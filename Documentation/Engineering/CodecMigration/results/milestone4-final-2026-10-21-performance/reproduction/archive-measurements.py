"""Validate the original-Consumer records and independently recompute comparisons."""
import collections
import hashlib
import json
import math
from pathlib import Path
import random
import statistics
import subprocess
import tempfile

KEYS = ('width', 'height', 'bits', 'pattern', 'components', 'near', 'interleave')
OPERATIONS = ('encode', 'decode', 'prepare', 'prepare_encode')
PRODUCERS = ('reference', 'candidate')


def require(condition, message):
    if not condition: raise ValueError(message)


def read(path): return json.loads(path.read_text())


def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''): digest.update(chunk)
    return digest.hexdigest()


def lines(path):
    with path.open() as stream: return [json.loads(line) for line in stream if line.strip()]


def same(actual, expected, label):
    if isinstance(expected, dict):
        require(isinstance(actual, dict), label + ': expected object')
        for key, value in expected.items():
            require(key in actual, label + ': missing ' + key)
            same(actual[key], value, label + '/' + key)
    elif isinstance(expected, list):
        require(isinstance(actual, list) and len(actual) == len(expected), label + ': wrong list length')
        for index, (a, b) in enumerate(zip(actual, expected)): same(a, b, f'{label}/{index}')
    elif isinstance(expected, float):
        require(type(actual) in (int, float) and math.isfinite(actual) and math.isclose(actual, expected, rel_tol=1e-11, abs_tol=1e-18), label + ': numerical disagreement')
    else:
        require(actual == expected, label + ': mismatch')


def percentile(values, fraction):
    position = (len(values) - 1) * fraction
    lo = int(position)
    hi = min(lo + 1, len(values) - 1)
    return values[lo] + (values[hi] - values[lo]) * (position - lo)


def intervals(values, seed):
    rng = random.Random(seed)
    bootstrap = sorted(statistics.median(rng.choices(values, k=16)) for _ in range(20000))
    ordered = sorted(values)
    return dict(percentile_bootstrap_95=[percentile(bootstrap, .025), percentile(bootstrap, .975)],
                exact_conservative_nominal_95=[ordered[3], ordered[12]], exact_coverage=0.978729248046875)


def owned_admission_identity(spec, root, bridge, build, benchmark, schedule, environment, completion, diagnostic, add, add_tree):
    """Validate the selected fourth candidate's distinct three-campaign plan.

    The production tree intentionally still held the preceding candidate during
    these isolated measurements. Its recorded identity is not the final source
    bridge, which is separately checked against the measured candidate bytes.
    """
    path = (root / spec['frozen_plan']).resolve()
    require(path.is_relative_to(root) and sha(path) == spec['frozen_plan_sha256'], 'Owned-admission fixed plan changed')
    frozen = read(path); folder = path.parent
    source = build['source']; candidate = frozen['candidate']; reference = frozen['three_change']
    require(candidate['build_identity_sha256'] == bridge['measured_candidate_build_sha256'] and
            candidate['binary_sha256'] == bridge['measured_binary_sha256'] and
            candidate['source_files'] == source['source_files'] and candidate['patches'] == source['patches'] and
            Path(candidate['build_identity_path']).resolve() == (root / bridge['measured_candidate_build']).resolve(),
            'Owned-admission selected source/build identity mismatch')
    reference_path = Path(reference['build_identity_path']).resolve()
    require(reference_path.is_relative_to(root) and sha(reference_path) == reference['build_identity_sha256'], 'Owned-admission preceding build changed')
    prior = read(reference_path)
    require(prior['source']['source_files'] == reference['source_files'] and prior['source']['patches'] == reference['patches'] and
            prior['binary_sha256'] == reference['binary_sha256'] and prior['source']['swift'] == source['swift'] and
            prior['source']['consumer_sha256'] == source['consumer_sha256'], 'Owned-admission reference identity mismatch')
    require(frozen['pinned']['source_commit'] == benchmark['predecessor_commit'] and
            frozen['pinned']['binary_sha256'] == benchmark['binary_sha256']['predecessor'] and
            frozen['production_head_at_plan'] == source['base_source'] == prior['source']['base_source'] and
            frozen['count_extension'] is frozen['metric_replacement'] is frozen['reruns'] is False,
            'Owned-admission baseline/protocol changed')
    for key, parent in [('script_sha256', folder), ('schedule_sha256', folder / 'schedules')]:
        for name, digest in frozen[key].items():
            require(Path(name).name == name and sha(parent / name) == digest, 'Owned-admission frozen input changed: ' + name)
    incremental = diagnostic is not None
    require(not incremental or diagnostic.get('category') == 'incremental_candidate', 'Owned-admission diagnostic must be explicitly incremental')
    mode = 'direct-short16' if incremental else 'pinned-short128' if spec['kind'] == 'tiny-confirmation128' else 'pinned-deep16'
    declared = [row for row in frozen['comparison_order'] if row['name'] == mode]
    require(len(declared) == 1 and len(frozen['comparison_order']) == 3 and frozen['total_processes'] == 1920, 'Owned-admission campaign selection changed')
    declared = declared[0]
    require((root / spec['root']).resolve() == folder / 'results' / mode and
            (root / spec['schedule']).resolve() == folder / 'schedules' / declared['schedule'] and
            (root / spec['runner']).resolve() == folder / declared['runner'] and
            schedule['expected_processes'] == declared['expected_processes'] and schedule['mode'] == declared['mode'] and
            schedule['reference'] == declared['reference'] and schedule['cases'] == frozen['cases'] and schedule['operations'] == frozen['operations'],
            'Owned-admission campaign does not match its fixed plan')
    expected_reference = reference['binary_sha256'] if incremental else frozen['pinned']['binary_sha256']
    require(schedule['producers']['reference']['sha256'] == expected_reference and
            schedule['producers']['candidate']['sha256'] == candidate['binary_sha256'] and
            schedule['producers']['candidate']['base_revision'] == source['base_source'] and
            schedule['producers']['candidate']['patch_sha256'] == source['patches']['combined.patch'], 'Owned-admission scheduled producer mismatch')
    if incremental:
        # The frozen three-change reference uses base_source; the selected
        # candidate uses base_revision. Keep their recorded schemas distinct.
        require(schedule['producers']['reference']['base_source'] == prior['source']['base_source'] and
                schedule['producers']['reference']['patch_sha256'] == prior['source']['patches']['combined.patch'], 'Incremental reference source changed')
    else:
        require(schedule['producers']['reference']['source'] == benchmark['predecessor_commit'], 'Owned-admission pinned source changed')
    for guards in (environment['source_guards'], completion['source_guards']):
        require(guards['plan_sha256'] == spec['frozen_plan_sha256'] and
                guards['candidate_build_identity_sha256'] == candidate['build_identity_sha256'] and
                guards['candidate_binary_sha256'] == candidate['binary_sha256'] and guards['candidate_source_files'] == source['source_files'] and
                guards['reference_build_identity_sha256'] == reference['build_identity_sha256'] and
                guards['reference_binary_sha256'] == reference['binary_sha256'] and
                guards['pinned_binary_sha256'] == frozen['pinned']['binary_sha256'] and
                guards['exact_production_tree_matches_three_change_reference'] is True,
                'Owned-admission measurement source guard mismatch')
        require(all(guards[key]['exit_code'] == 0 for key in ('production_head', 'pinned_head', 'pinned_diff', 'swift')) and
                guards['production_head']['output'].strip() == frozen['production_head_at_plan'] and
                guards['pinned_head']['output'].strip() == benchmark['predecessor_commit'] and
                guards['swift']['stdout'] == source['swift'], 'Owned-admission head/compiler guard failed')
    for label, identity in [('candidate', build), ('three_change', prior)]:
        origin = Path(frozen[label]['build_identity_path']).parent
        for item in frozen[label]['validation_files'] + frozen[label]['preflight_files']:
            evidence = (origin / item['path']).resolve()
            require(evidence.is_relative_to(origin) and sha(evidence) == item['sha256'], 'Owned-admission validation/preflight changed')
            add(evidence, ('measured-candidate/' if label == 'candidate' else 'preceding-candidate/') + item['path'])
    preflight = build['preflight']
    require(preflight['all_six_passed'] is True and len(preflight['cases']) == 6 and
            {row['case'] for row in preflight['cases']} == {f'37x23-{pattern}-p{bits}' for bits in (12, 16) for pattern in ('flat', 'ramp', 'noise')} and
            all(row['exit_code'] == 0 and row['full_sample_verification'] == 'passed' for row in preflight['cases']),
            'Owned-admission candidate correctness preflight failed')
    commands = read(folder / 'commands.json')
    require([row['comparison'] for row in commands] == [row['name'] for row in frozen['comparison_order']] and
            all(row['exit_code'] == 0 for row in commands), 'Owned-admission three-campaign execution incomplete')
    prefix = 'performance/owned-admission-provenance'
    for pattern in ('*.py', '*.json', '*.log', '*.md'):
        for item in folder.glob(pattern): add(item, prefix + '/' + item.name)
    add_tree(folder / 'schedules', prefix + '/schedules')
    correction = read(folder / 'preparation-attempt-1/failure.json')
    require(correction['measured_processes'] == 0, 'Preparation correction unexpectedly contains measurements')
    add_tree(folder / 'preparation-attempt-1', prefix + '/preparation-attempt-1')
    return frozen


def validate(spec, root, bridge, build, benchmark, larger_plan, add, add_tree, diagnostic=None):
    def resolve(relative):
        path = (root / relative).resolve()
        require(path.is_relative_to(root), 'Measurement path escapes repository')
        return path
    folder, schedule_path, runner = (resolve(spec[key]) for key in ('root', 'schedule', 'runner'))
    kind, name = spec['kind'], spec['name']
    require(kind in ('tiny-short', 'tiny-deep', 'larger', 'diagnostic-short', 'tiny-confirmation128'), 'Unknown measurement kind')
    require(kind != 'diagnostic-short' or diagnostic is not None, 'Diagnostic scope requires its explicit identity validator')
    require(diagnostic is None or kind == 'diagnostic-short' or diagnostic.get('category') == 'preceding_candidate',
            'Only an explicitly classified preceding candidate can reuse the measured-campaign schema as diagnostic evidence')
    plan, environment, completion = read(schedule_path), read(folder / 'environment.json'), read(folder / 'complete.json')
    schedule_digest, runner_digest = sha(schedule_path), sha(runner)
    require(environment['plan'] == plan and environment['schedule_sha256'] == completion['schedule_sha256'] == schedule_digest,
            name + ': schedule identity changed')
    require(environment['runner_sha256'] == completion['runner_sha256'] == runner_digest,
            name + ': runner identity changed')
    require(environment['consumer_sha256'] == bridge['consumer_sha256'], name + ': different common Consumer')
    require(completion['completed'] is True and completion['performance_qualified'] is False and environment['performance_qualified'] is False,
            name + ': incomplete campaign or automatic acceptance claim')
    blocks, warmups, observations = (128, 5, 5) if kind == 'tiny-confirmation128' else (16, 5, 5) if kind in ('tiny-short', 'diagnostic-short') else (16, 20000, 1000) if kind == 'tiny-deep' else (4, 5, 5)
    require(plan['blocks_per_case'] == blocks and plan['warmups'] == warmups and plan['observations_per_process'] == observations and tuple(plan['operations']) == OPERATIONS,
            name + ': wrong declared repetition protocol')
    cases = {row['id']: row for row in plan['cases']}
    require(len(cases) == len(plan['cases']), name + ': duplicate case IDs')
    profiles = {tuple(row[k] for k in KEYS) for row in cases.values()}
    expected = ({(37, 23, bits, pattern, 1, 0, 0) for bits in (12, 16) for pattern in ('flat', 'ramp', 'noise')}
                if kind != 'larger' else {tuple(row[k] for k in KEYS) for row in larger_plan['cases']})
    require(len(profiles) == len(cases) and profiles == expected, name + ': case selection changed or incomplete')
    if kind == 'larger':
        digest = sha(resolve(spec['larger_guard_plan']))
        require(plan['larger_guard_plan_sha256'] == environment['larger_guard_plan_sha256'] == completion['larger_guard_plan_sha256'] == digest,
                name + ': predeclared larger plan changed')
    source = build['source']
    hashes = diagnostic['hashes'] if diagnostic is not None else {'reference': benchmark['binary_sha256']['predecessor'], 'candidate': bridge['measured_binary_sha256']}
    require(set(plan['producers']) == set(PRODUCERS), name + ': producers changed')
    owned_admission = spec.get('identity_schema') == 'owned-admission-v1'
    require(spec.get('identity_schema') in (None, 'owned-admission-v1'), 'Unknown measurement identity schema')
    if owned_admission:
        owned_frozen = owned_admission_identity(spec, root, bridge, build, benchmark, plan, environment, completion, diagnostic, add, add_tree)
    elif diagnostic is not None:
        diagnostic['validate_identity'](plan, environment, completion)
    else:
        require(plan['producers']['reference']['source'] == benchmark['predecessor_commit'], name + ': predecessor changed')
        require(plan['producers']['candidate']['base_revision'] == source['base_source'] and
            plan['producers']['candidate']['patch_sha256'] == source['patches']['combined.patch'] and
            all(plan['producers'][producer]['sha256'] == hashes[producer] for producer in PRODUCERS), name + ': candidate identity mismatch')
    for guards in (() if diagnostic is not None or owned_admission else (environment['source_guards'], completion['source_guards'])):
        require(guards['candidate_source_hashes'] == source['source_files'] and
                guards['candidate_build_identity_sha256'] == bridge['measured_candidate_build_sha256'] and
                guards['candidate_patch_sha256'] == source['patches']['combined.patch'] and
                guards['candidate_binary_sha256'] == hashes['candidate'], name + ': candidate input guard mismatch')
        require(guards['successor_head']['output'].strip() in {source['base_source'], bridge['source_commit']} and
                guards['predecessor_head']['output'].strip() == benchmark['predecessor_commit'] and
                all(guards[key]['exit_code'] == 0 for key in ('successor_head', 'predecessor_head', 'predecessor_diff')),
                name + ': source head/diff guards failed')
        if kind == 'larger':
            evidence_root = Path(__file__).resolve().parent
            require(guards['source_commit'] == guards['successor_head']['output'].strip() == bridge['source_commit'] and
                    guards['successor_status']['exit_code'] == 0 and not guards['successor_status']['output'].strip() and
                    guards['fixtures']['exit_code'] == 0 and guards['fixtures']['output'].strip() == source['fixtures_tree'] and
                    guards['swift']['exit_code'] == 0 and guards['swift']['stdout'] == source['swift'] and
                    guards['benchmark_reuse_sha256'] == sha(evidence_root / 'benchmark-reuse.json') and
                    guards['benchmark_build_sha256'] == sha(evidence_root / 'benchmark-build.json') and
                    guards['larger_guard_plan_sha256'] == sha(resolve(spec['larger_guard_plan'])),
                    name + ': promoted-source status/compiler/reuse guards failed')
        else:
            require(guards['successor_diff']['exit_code'] == 0, name + ': candidate-base source diff failed')
    schedule = plan['schedule']
    require(len(schedule) == blocks * len(cases), name + ': missing schedule entries')
    require({(entry['case']['id'], entry['block']) for entry in schedule} == {(case, block) for case in cases for block in range(blocks)},
            name + ': schedule omitted/duplicated a paired case block')
    for case_id in cases:
        entries = [entry for entry in schedule if entry['case']['id'] == case_id]
        require(collections.Counter(entry['order'][0] for entry in entries) == {producer: blocks // 2 for producer in PRODUCERS}, name + ': unbalanced producer order')
    expected_order = [(entry, producer) for entry in schedule for producer in entry['order']]
    raw = lines(folder / 'raw.jsonl')
    require(len(raw) == plan['expected_processes'] == completion['processes'] == len(expected_order) == blocks * len(cases) * 2,
            name + ': incomplete process count')
    for (entry, producer), row in zip(expected_order, raw):
        require(entry['case'] == cases[entry['case']['id']] and sorted(entry['order']) == sorted(PRODUCERS), name + ': malformed schedule entry')
        require(row['exit_code'] == 0 and row['producer'] == row['label'] == producer and row['block'] == entry['block'] and
                row['case_id'] == entry['case']['id'] and row['position'] == entry['position'] and row['order'] == entry['order'] and
                row['binary_sha256'] == hashes[producer] and row['warmups'] == warmups and row['iterations'] == observations and
                row['end_to_end'] is True and row['resource_profile'] == 'successor-workspace-1GiB-memory-2GiB-v1' and
                all(row[k] == entry['case'][k] for k in KEYS), name + ': raw process differs from schedule')
        for operation in OPERATIONS:
            values = row[operation + '_seconds']
            require(len(values) == observations and all(type(v) in (int, float) and math.isfinite(v) and v >= 0 for v in values), name + ': invalid duration')
        require(all(a >= b for a, b in zip(row['prepare_encode_seconds'], row['prepare_seconds'])), name + ': invalid combined timing')
        require(row['encoded_bytes'] > 0 and row['peak_process_rss_bytes'] > 0, name + ': missing size/RSS observations')
    bootstrap_metrics, bootstrap_provenance = {}, None
    if kind == 'tiny-confirmation128':
        frozen_path = resolve(spec['frozen_plan'])
        frozen = read(frozen_path)
        require(isinstance(spec['frozen_plan_sha256'], str) and len(spec['frozen_plan_sha256']) == 64 and sha(frozen_path) == spec['frozen_plan_sha256'],
                'Predeclared 128-round plan changed')
        if owned_admission:
            inference = frozen['primary_short_analysis']
            require(frozen == owned_frozen and frozen['script_sha256'][runner.name] == runner_digest and
                    frozen['schedule_sha256'][schedule_path.name] == schedule_digest and
                    inference['seed'] == 20261021 and inference['resamples'] == 50000 and inference['family_size'] == 24 and
                    inference['familywise_quantiles'] == [1 / 960, 959 / 960] and inference['marginal_quantiles'] == [.025, .975] and
                    inference['numpy'] == '2.3.5' and inference['quantile_method'] == 'linear', 'Owned-admission128 fixed inference changed')
            analysis_digest = frozen['script_sha256']['analyse.py']
            require(inference['source_script_sha256'] == analysis_digest, 'Owned-admission128 no longer uses original pooled analysis')
            self_test = frozen_path.parent / 'inherited-analysis-self-test.json'
            self_test_digest = frozen['unchanged_primary_analysis_self_test_sha256']
            analysis_python = spec['analysis_python']
            require(str(analysis_python) in runner.read_text(), 'Analysis runtime differs from the frozen runner')
        else:
            require(frozen['runner_sha256'] == runner_digest and frozen['schedule_sha256'] == schedule_digest and
                    frozen['candidate_build_identity_sha256'] == bridge['measured_candidate_build_sha256'] and
                    frozen['expected_processes'] == 1536 and frozen['paired_rounds'] == 128 and frozen['metrics'] == 24 and
                    frozen['warmups'] == frozen['observations'] == 5 and frozen['seed'] == 20261021 and frozen['bootstrap_resamples'] == 50000 and
                    frozen['count_extension'] is frozen['metric_replacement'] is frozen['reruns'] is False,
                    '128-round fixed protocol changed')
            analysis_digest = frozen['analysis_sha256']
            self_test = frozen_path.parent / 'analysis-self-test.json'
            self_test_digest = frozen['analysis_self_test_sha256']
            analysis_python = frozen['analysis_python']
        require(all(entry['order'] == (['reference', 'candidate'] if entry['block'] % 2 == 0 else ['candidate', 'reference']) for entry in schedule),
                '128-round shared producer-order strata changed')
        analysis_path = frozen_path.parent / 'analyse.py'
        require(sha(analysis_path) == analysis_digest and sha(self_test) == self_test_digest and read(self_test)['passed'] is True,
                'Frozen pooled analysis or self-test changed')
        for item in (environment['source_guards'], completion['source_guards']):
            require(item['plan_sha256'] == sha(frozen_path) and (owned_admission or item['analysis_sha256'] == analysis_digest),
                    '128-round analysis identity guard changed')
        measured = read(folder / 'measurement-complete.json')
        require(measured['completed'] is True and measured['processes'] == 1536 and measured['plan_sha256'] == completion['plan_sha256'] == sha(frozen_path) and
                measured['source_guards'] == completion['source_guards'] and completion['analysis_sha256'] == analysis_digest and
                read(folder / 'analysis-command.json')['exit_code'] == 0, '128-round measurement/analysis completion mismatch')
        # Run a separate read-only-input implementation using the frozen NumPy
        # runtime. This occurs only during archive validation after timings end.
        helper = Path(__file__).with_name('archive-confirmation-bootstrap.py')
        with tempfile.TemporaryDirectory(prefix='m4-bootstrap-verification-') as temporary:
            output = Path(temporary) / 'recomputed.json'
            command = [analysis_python, str(helper), '--raw', str(folder / 'raw.jsonl'),
                       '--schedule', str(schedule_path), '--output', str(output)]
            process = subprocess.run(command, capture_output=True, text=True)
            require(process.returncode == 0, 'Independent 128-round bootstrap failed: ' + process.stderr)
            recomputed = read(output)
        metadata = read(folder / 'bootstrap-metadata.json')
        same(metadata, {key: value for key, value in recomputed.items() if key != 'metrics'}, '128-round bootstrap metadata')
        require(metadata['raw_sha256'] == sha(folder / 'raw.jsonl') and metadata['schedule_sha256'] == schedule_digest and
                metadata['script_sha256'] == analysis_digest, '128-round bootstrap raw/script identity mismatch')
        bootstrap_metrics = {(row['case'], row['operation']): row for row in recomputed['metrics']}
        bootstrap_provenance = dict(frozen_plan_sha256=sha(frozen_path), helper_sha256=sha(helper), command=command,
                                    exit_code=process.returncode, stdout=process.stdout, stderr=process.stderr,
                                    recomputed_metadata={key: value for key, value in recomputed.items() if key != 'metrics'})
        for path in [frozen_path, analysis_path, self_test]: add(path, 'performance/' + name + '/' + path.name)
        for pattern in ('*.py', '*.json', '*.md', '*.log'):
            for path in frozen_path.parent.glob(pattern):
                if path not in (frozen_path, analysis_path, self_test):
                    add(path, 'performance/' + name + '/provenance/' + path.name)
    recorded = read(folder / 'summary.json')
    require(len(recorded) == len(cases) and {row['case']['id'] for row in recorded} == set(cases), name + ': summary selection differs')
    recorded = {row['case']['id']: row for row in recorded}
    results = []
    for case_index, case in enumerate(plan['cases']):
        selected = [row for row in raw if row['case_id'] == case['id']]
        result = dict(case=case, operations={})
        for operation_index, operation in enumerate(OPERATIONS):
            pooled = {producer: [v for row in selected if row['producer'] == producer for v in row[operation + '_seconds']] for producer in PRODUCERS}
            medians = {producer: statistics.median(values) for producer, values in pooled.items()}
            require(all(value > 0 for value in medians.values()), name + ': zero median cannot define a ratio')
            pairs = []
            for block in range(blocks):
                pair = {row['producer']: row for row in selected if row['block'] == block}
                med = {producer: statistics.median(row[operation + '_seconds']) for producer, row in pair.items()}
                require(med['reference'] > 0, name + ': zero block reference median')
                pairs.append(dict(block=block, order=pair['candidate']['order'], reference_median_seconds=med['reference'],
                    candidate_median_seconds=med['candidate'], ratio=med['candidate'] / med['reference'], delta_seconds=med['candidate'] - med['reference']))
            ratios, deltas = [p['ratio'] for p in pairs], [p['delta_seconds'] for p in pairs]
            ordered = sorted(ratios)
            metric = dict(pooled_median_seconds=medians, pooled_ratio=medians['candidate'] / medians['reference'],
                observations_per_producer=blocks * observations, median_block_ratio=statistics.median(ratios),
                median_block_delta_seconds=statistics.median(deltas), ratio_range=[min(ratios), max(ratios)],
                ratio_iqr=[percentile(ordered, .25), percentile(ordered, .75)], ratio_sample_standard_deviation=statistics.stdev(ratios),
                blocks_above_1_05=sum(ratio > 1.05 for ratio in ratios),
                median_ratio_by_first_producer={producer: statistics.median(p['ratio'] for p in pairs if p['order'][0] == producer) for producer in PRODUCERS}, pairs=pairs)
            if blocks == 16:
                seed = 20261021 + case_index * 10 + operation_index
                metric.update(ratio_intervals=intervals(ratios, seed), delta_intervals_seconds=intervals(deltas, seed))
            check = metric
            if blocks == 128:
                inference = bootstrap_metrics[case['id'], operation]
                order_groups = {}
                for first in PRODUCERS:
                    subset = [row for row in selected if row['order'][0] == first]
                    pooled_order = {producer: statistics.median(value for row in subset if row['producer'] == producer for value in row[operation + '_seconds']) for producer in PRODUCERS}
                    order_groups[first] = dict(rounds=64, pooled_ratio=pooled_order['candidate'] / pooled_order['reference'],
                        median_block_ratio=statistics.median(pair['ratio'] for pair in pairs if pair['order'][0] == first))
                temporal = []
                for first in range(0, 128, 16):
                    subset = [row for row in selected if first <= row['block'] < first + 16]
                    med = {producer: statistics.median(value for row in subset if row['producer'] == producer for value in row[operation + '_seconds']) for producer in PRODUCERS}
                    temporal.append(dict(first_round=first, last_round=first + 15, pooled_ratio=med['candidate'] / med['reference'],
                        median_block_ratio=statistics.median(pair['ratio'] for pair in pairs if first <= pair['block'] < first + 16)))
                metric.update(paired_rounds=128, familywise_bonferroni_95=inference['familywise_bonferroni_95'],
                    marginal_95=inference['marginal_95'], interpretation=inference['interpretation'], order_groups=order_groups, temporal_groups=temporal)
                check = {key: value for key, value in metric.items() if key not in ('ratio_sample_standard_deviation', 'median_ratio_by_first_producer')}
            same(recorded[case['id']]['operations'][operation], check, name + '/' + case['id'] + '/' + operation)
            result['operations'][operation] = metric
        for field in ('encoded_bytes', 'peak_process_rss_bytes'):
            observed = {producer: [row[field] for row in selected if row['producer'] == producer] for producer in PRODUCERS}
            if field == 'encoded_bytes':
                require(all(len(set(values)) == 1 for values in observed.values()), name + ': encoded size changed within a case/producer')
            medians = {producer: statistics.median(values) for producer, values in observed.items()}
            result[field] = dict(observations=observed, median=medians, ratio=medians['candidate'] / medians['reference'])
        results.append(result)
    conditions = [environment['conditions'], *lines(folder / 'conditions.jsonl'), completion['end_conditions']]
    require(all(row['power']['exit_code'] == 0 and "Now drawing from 'AC Power'" in row['power']['output'] for row in conditions), name + ': non-AC/unknown observation')
    require(all(row['thermal']['exit_code'] == 0 and
                'No thermal warning level has been recorded' in row['thermal']['output'] and
                'No performance warning level has been recorded' in row['thermal']['output'] for row in conditions),
            name + ': missing or failed thermal/performance admission observation')
    add(schedule_path, 'performance/' + name + '/schedule.json')
    add(runner, 'performance/' + name + '/runner.py')
    add_tree(folder, 'performance/' + name)
    return dict(name=name, kind=kind, cases=results, paired_blocks=blocks, processes=len(raw),
                warmups=warmups, observations_per_process=observations, schedule_sha256=schedule_digest,
                runner_sha256=runner_digest, condition_observations=len(conditions),
                thermal_observations=[row.get('thermal') for row in conditions],
                source_bridge=bridge['source_commit'] if diagnostic is None else None,
                diagnostic_scope=diagnostic['scope'] if diagnostic is not None else None,
                diagnostic_category=diagnostic.get('category') if diagnostic is not None else None,
                measured_candidate_base=source['base_source'],
                measured_binary_sha256=hashes, bootstrap_verification=bootstrap_provenance, automatic_acceptance=False)
