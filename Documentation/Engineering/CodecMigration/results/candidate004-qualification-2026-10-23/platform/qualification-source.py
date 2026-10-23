#!/usr/bin/env python3
"""Pin candidate004 without relabelling the uncommitted snapshot as a Git commit."""
import hashlib
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent
PINS = json.loads((OUT / 'pins.json').read_text())
ROOT = Path(PINS['source_root'])


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')


def source():
    if sha(PINS['source_receipt']) != PINS['source_receipt_sha256']:
        raise RuntimeError('Candidate004 preparation receipt changed.')
    for root in [ROOT, Path(PINS['live_root'])]:
        for folder, key in [('Sources/SwiftJLS', 'production'), ('Tests/SwiftJLSTests', 'tests')]:
            actual = {str(p.relative_to(root)): sha(p) for p in (root / folder).rglob('*.swift')}
            if actual != PINS[key]:
                raise RuntimeError(f'Frozen source inventory changed: {root / folder}')
    for name, expected in PINS['files'].items():
        if sha(ROOT / name) != expected:
            raise RuntimeError(f'Qualification input changed: {name}')
    return dict(source_id='candidate_004', base_head=PINS['base_head'], source_commit=None,
                source_receipt_sha256=PINS['source_receipt_sha256'],
                sources_patch_sha256=PINS['sources_patch_sha256'],
                source_manifest_sha256=PINS['source_manifest_sha256'],
                production_file_count=len(PINS['production']), test_swift_count=len(PINS['tests']),
                expected_test_declarations=152, files=PINS['files'])


def unchanged(before):
    if source() != before:
        raise RuntimeError('Candidate source changed during qualification.')
