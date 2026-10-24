#!/usr/bin/env python3
"""Materialise a fresh, unpromoted three-part candidate from the pinned source."""
import datetime, hashlib, json, os, pathlib, subprocess, tarfile

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
BASE = 'bee49a2ad47eae4ea149bdced2043b7a45df3dae'
CODEC = HERE / 'codec'
CONSUMER = HERE / 'consumer'
ENV = dict(os.environ, DEVELOPER_DIR='/Library/Developer/CommandLineTools')

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def command(args, cwd=ROOT):
    return subprocess.check_output(args, cwd=cwd, env=ENV, text=True)

if CODEC.exists() or CONSUMER.exists():
    raise SystemExit('Refusing to overwrite an existing candidate or its evidence.')
CODEC.mkdir()
process = subprocess.Popen(['git', 'archive', BASE, 'Package.swift', 'VERSION', 'Sources', 'Tests'], cwd=ROOT, stdout=subprocess.PIPE)
with tarfile.open(fileobj=process.stdout, mode='r|') as archive:
    for member in archive:
        path = pathlib.PurePosixPath(member.name)
        assert not path.is_absolute() and '..' not in path.parts
        assert member.isfile() or member.isdir()
        archive.extract(member, CODEC)
if process.wait() != 0:
    raise SystemExit('Source materialisation failed.')

patch_inputs = {
    'singleton.patch': ROOT / 'work/m4-singleton-parser-diagnostic/singleton.patch',
    'parser.patch': ROOT / 'work/m4-singleton-parser-diagnostic/parser.patch',
    'gradient.patch': ROOT / 'work/m4-decoder-gradient-diagnostic/candidate.patch',
}
for name, path in patch_inputs.items():
    patch = HERE / name
    patch.write_bytes(path.read_bytes())
    args = ['git', 'apply', '--directory=' + str(CODEC.relative_to(ROOT)), str(patch)]
    subprocess.run(args[:2] + ['--check'] + args[2:], cwd=ROOT, check=True)
    subprocess.run(args, cwd=ROOT, check=True)
(HERE / 'combined.patch').write_bytes(b'\n'.join((HERE / name).read_bytes() for name in patch_inputs))

(CONSUMER / 'Sources/Benchmark').mkdir(parents=True)
original = subprocess.check_output(['git', 'show', BASE + ':Scripts/Benchmark/Consumer.swift'], cwd=ROOT)
(CONSUMER / 'Sources/Benchmark/main.swift').write_bytes(original)
(CONSUMER / 'Package.swift').write_bytes((ROOT / 'work/m4-singleton-parser-diagnostic/consumer/Package.swift').read_bytes())
assert sha(CONSUMER / 'Sources/Benchmark/main.swift') == '27e4ca75529bf1a0e27ae4be14ec6c906945cc2ee6f0fa22170594144fe00c34'
files = sorted([CODEC / 'Package.swift', CODEC / 'VERSION', *CODEC.glob('Sources/**/*.swift'), *CODEC.glob('Tests/**/*.swift')])
record = {
    'created_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
    'base_source': BASE,
    'label': 'Unpromoted bee49a2 + singleton mapping + parser containers + decoder interval table',
    'patches': {name: sha(HERE / name) for name in [*patch_inputs, 'combined.patch']},
    'source_files': {str(p.relative_to(CODEC)): sha(p) for p in files},
    'fixtures_tree': command(['git', 'rev-parse', BASE + ':Tests/SwiftJLSTests/Fixtures']).strip(),
    'fixture_materialisation': 'Exact git archive of pinned base Tests; no fixture modifications',
    'consumer_sha256': sha(CONSUMER / 'Sources/Benchmark/main.swift'),
    'consumer_package_sha256': sha(CONSUMER / 'Package.swift'),
    'developer_dir': ENV['DEVELOPER_DIR'],
    'swift': command(['swift', '--version']),
    'status': 'Prepared; no validation or timings yet',
}
(HERE / 'source-identity.json').write_text(json.dumps(record, indent=2) + '\n')
print(json.dumps({k:v for k,v in record.items() if k != 'source_files'}, indent=2))
