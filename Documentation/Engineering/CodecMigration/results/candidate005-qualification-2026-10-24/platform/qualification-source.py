#!/usr/bin/env python3
"""Pin candidate005 without relabelling the uncommitted snapshot as a Git commit."""
import hashlib
import json
import os
from pathlib import Path

OUT = Path(__file__).resolve().parent
PINS = json.loads((OUT / 'pins.json').read_text())
if PINS.get('status') != 'frozen_candidate005':
    raise RuntimeError('Candidate005 platform source/host pins are not frozen; execution is forbidden.')
if os.environ.get('SWIFTJLS_PLATFORM_VALIDATION_RELEASE') != 'candidate005':
    raise RuntimeError('Explicit root post-timing release is required before platform execution.')
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
    if sha(PINS['source_inventory_path']) != PINS['source_inventory_sha256']:
        raise RuntimeError('Root source inventory changed.')
    if sha(PINS['supplemental_input_receipt']) != PINS['supplemental_input_receipt_sha256']:
        raise RuntimeError('Supplemental CLI input receipt changed.')
    for root in [ROOT, Path(PINS['live_root'])]:
        for folder, key in [('Sources/SwiftJLS', 'production'), ('Tests/SwiftJLSTests', 'tests')]:
            actual = {str(p.relative_to(root)): sha(p) for p in (root / folder).rglob('*.swift')}
            if actual != PINS[key]:
                raise RuntimeError(f'Frozen source inventory changed: {root / folder}')
    for name, expected in PINS['files'].items():
        if sha(ROOT / name) != expected:
            raise RuntimeError(f'Qualification input changed: {name}')
    return dict(source_id='candidate_005', base_head=PINS['base_head'], source_commit=None,
                source_receipt_sha256=PINS['source_receipt_sha256'],
                sources_patch_sha256=PINS['sources_patch_sha256'],
                source_manifest_sha256=PINS['source_manifest_sha256'],
                production_file_count=len(PINS['production']), test_swift_count=len(PINS['tests']),
                expected_test_declarations=PINS['expected_declarations'], files=PINS['files'])


def unchanged(before):
    if source() != before:
        raise RuntimeError('Candidate source changed during qualification.')
