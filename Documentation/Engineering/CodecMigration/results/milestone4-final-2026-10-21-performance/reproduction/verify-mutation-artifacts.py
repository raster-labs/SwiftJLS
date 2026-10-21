#!/usr/bin/env python3
"""Independently reconcile the already-collected, source-specific mutation run."""
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent / 'mutation'
RUN = 39623942298
SOURCE = 'e6a6436c692f5af226bffceb70b7ee65c774edf3'

def require(value, message):
    if not value:
        raise ValueError(message)

def sha(data):
    return hashlib.sha256(data).hexdigest()

def load(path):
    return json.loads(path.read_text())

run = load(OUT / 'run.json')
source = load(OUT / 'source.json')
artifacts = load(OUT / 'artifact-metadata.json')
require(run['databaseId'] == RUN and run['headSha'] == SOURCE, 'Run/source identity mismatch')
require(source['run_id'] == RUN and source['revision'] == SOURCE and source['run_head_sha'] == SOURCE,
        'Collector source binding mismatch')
require(run['status'] == 'completed' and run['conclusion'] == 'success', 'Run incomplete')
require(len(run['jobs']) == 3 and all(j['conclusion'] == 'success' for j in run['jobs']), 'Job failures')
require(artifacts['total_count'] == 3 and len(artifacts['artifacts']) == 3, 'Expected three mutation artifacts')
expected_files = {'campaign-result.json', 'campaign.jsonl', 'campaign-stderr.log', 'last-input.jls'}
result = dict(run_id=RUN, revision=SOURCE, run_url=run['url'], entries={}, passed=False,
              scope='Only the explicitly authorised source-specific mutation experiment; no general CI verification.')
for entry in ['owned', 'into', 'inspect']:
    matches = [a for a in artifacts['artifacts'] if a['name'] == 'mutation-' + entry]
    require(len(matches) == 1, 'Missing or duplicate artifact ' + entry)
    artifact = matches[0]
    require(not artifact['expired'] and artifact['workflow_run']['id'] == RUN
            and artifact['workflow_run']['head_sha'] == SOURCE, 'Artifact/source mismatch ' + entry)
    archive = OUT / ('mutation-' + entry + '.zip')
    archive_sha = sha(archive.read_bytes())
    require(artifact['digest'] == 'sha256:' + archive_sha, 'Remote artifact digest mismatch ' + entry)
    require(archive.stat().st_size == artifact['size_in_bytes'], 'Remote artifact size mismatch ' + entry)
    folder = OUT / entry
    with zipfile.ZipFile(archive) as z:
        require(set(z.namelist()) == expected_files, 'Unexpected artifact contents ' + entry)
        for name in expected_files:
            data = (folder / name).read_bytes()
            require(z.read(name) == data, 'Extracted file differs from original ZIP ' + entry + '/' + name)
            retained = source['artifact_hashes'][entry][name]
            require(retained['sha256'] == sha(data) and retained['bytes'] == len(data), 'Collector hash mismatch')
    rows = [json.loads(line) for line in (folder / 'campaign.jsonl').read_text().splitlines()]
    require(len(rows) > 1 and all(not r.get('complete', False) for r in rows[:-1]), 'Unexpected completion rows')
    previous = dict(seconds=0, iterations=0, accepted=0, rejected=0, decodeCalls=0)
    largest_gap = 0
    for row in rows:
        require(row['entry'] == entry and row['accepted'] + row['rejected'] == row['iterations'], 'Heartbeat count mismatch')
        require(all(row[k] >= previous[k] for k in previous), 'Non-monotonic heartbeat')
        require(row['iterations'] > previous['iterations'], 'No progress between heartbeats')
        if entry == 'owned':
            require(row['decodeCalls'] == row['iterations'], 'Owned decode count mismatch')
        elif entry == 'inspect':
            require(row['decodeCalls'] == 0, 'Inspect unexpectedly decodes')
        else:
            require(row['accepted'] <= row['decodeCalls'] <= row['iterations'], 'Into decode count mismatch')
        largest_gap = max(largest_gap, row['seconds'] - previous['seconds'])
        previous = {k: row[k] for k in previous}
    final = rows[-1]
    supervisor = load(folder / 'campaign-result.json')
    require(final['complete'] and 3600 <= final['seconds'] <= 3645, 'Incomplete or over-budget campaign')
    require(final['generatorSeed'] == '0x4a4c5301' and final['seedCount'] == 981, 'Corpus/generator mismatch')
    require(supervisor['command'][2:4] == [entry, '3600'], 'Unexpected entry/duration command')
    require(supervisor['exit_code'] == 0 and supervisor['failure'] is None, 'Supervisor failure')
    require(final['seconds'] <= supervisor['wall_seconds'] <= 3645, 'Supervisor timing mismatch')
    require(largest_gap <= 30, 'Heartbeat gap exceeded supervisor limit')
    require((folder / 'campaign-stderr.log').stat().st_size == 0, 'Nonempty sanitizer stderr')
    require(final == source['entries'][entry]['final'] and supervisor == source['entries'][entry]['supervisor'],
            'Source report differs from raw campaign')
    result['entries'][entry] = dict(artifact_id=artifact['id'], artifact_name=artifact['name'],
        artifact_sha256=archive_sha, artifact_bytes=archive.stat().st_size,
        heartbeat_records=len(rows)-1, largest_heartbeat_gap_seconds=largest_gap,
        iterations=final['iterations'], accepted=final['accepted'], rejected=final['rejected'],
        decode_calls=final['decodeCalls'], seconds=final['seconds'],
        supervisor_wall_seconds=supervisor['wall_seconds'], stderr_bytes=0,
        seed_count=final['seedCount'], generator_seed=final['generatorSeed'],
        all_counts_reconciled=True, zip_contents_equal_collected_files=True)
result['totals'] = {k: sum(e[k] for e in result['entries'].values())
                    for k in ['iterations', 'accepted', 'rejected', 'decode_calls']}
require(result['totals']['accepted'] + result['totals']['rejected'] == result['totals']['iterations'], 'Total count mismatch')
result['passed'] = True
result['verification_script_sha256'] = sha(Path(__file__).read_bytes())
(OUT / 'artifact-verification.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps(result, indent=2))
