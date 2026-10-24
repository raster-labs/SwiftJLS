#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Prove ordinary allocator telemetry sees a hidden full-frame encode copy.

Builds only in a temporary clone. The consumer's sample/identity/report checks
must still pass: the independent allocator trace must expose the injected copy.
"""
import argparse
import hashlib
import json
import pathlib
import shutil
import subprocess
import tempfile

parser = argparse.ArgumentParser()
parser.add_argument('--baseline', type=pathlib.Path, required=True)
parser.add_argument('--output', type=pathlib.Path, required=True)
args = parser.parse_args()
root = pathlib.Path(__file__).resolve().parents[2]
output = args.output.resolve()
output.mkdir(parents=True, exist_ok=True)
source = root / 'Sources/SwiftJLS/JPEGLS/ScalarCodec.swift'
original = source.read_text()
needle = '    static func encode(_ image: Image, configuration: EncoderConfiguration, options: EncodeOptions) throws -> EncodedImage {\n'
if original.count(needle) != 1:
    raise RuntimeError('Expected one scalar encoder boundary')
helper = '''
    @inline(never) static func telemetryInjectedFrameCopy(_ source: Image, limits: ResourceLimits) throws -> Image {
        let target = try ImageDestination.allocate(descriptor: source.descriptor, limits: limits)
        return try target.write { destination in
            try source.storage.withUnsafeBytes { input in
                destination.copyMemory(from: UnsafeRawBufferPointer(rebasing: input.prefix(destination.count)))
            }
        }
    }
'''
mutated = original.replace(needle, helper + needle + '        let image = try telemetryInjectedFrameCopy(image, limits: options.resourceLimits)\n')
marker = 'telemetryInjectedFrameCopy'
baseline = (args.baseline / 'analysis-demangled.txt').read_text()
if marker in baseline:
    raise RuntimeError('Injected allocation already present in baseline')
commands = []
with tempfile.TemporaryDirectory(prefix='swiftjls-copy-mutation-') as temporary:
    checkout = pathlib.Path(temporary) / 'SwiftJLS'
    checkout.mkdir()
    shutil.copy2(root / 'Package.swift', checkout)
    for directory in ['Sources', 'Tests']:
        shutil.copytree(root / directory, checkout / directory)
    consumer = checkout / 'Examples/CrossCodecConsumer'
    shutil.copytree(root / 'Examples/CrossCodecConsumer', consumer,
                    ignore=shutil.ignore_patterns('.build', '.swiftpm'))
    (checkout / 'Sources/SwiftJLS/JPEGLS/ScalarCodec.swift').write_text(mutated)
    command = ['swift', 'build', '-c', 'release', '-Xswiftc', '-g', '--package-path', str(consumer)]
    result = subprocess.run(command, capture_output=True, timeout=300)
    (output / 'build.stdout').write_bytes(result.stdout)
    (output / 'build.stderr').write_bytes(result.stderr)
    commands.append(dict(command=command, exit_code=result.returncode))
    result.check_returncode()
    command = ['python3', str(root / 'Scripts/StorageEvidence/trace-heap.py'), '--binary',
               str(consumer / '.build/release/CrossCodecConsumer'), '--output', str(output / 'mutant')]
    result = subprocess.run(command, capture_output=True, timeout=240)
    (output / 'trace.stdout').write_bytes(result.stdout)
    (output / 'trace.stderr').write_bytes(result.stderr)
    commands.append(dict(command=command, exit_code=result.returncode))
    result.check_returncode()
    analysis = (output / 'mutant/analysis-demangled.txt').read_text()
    # Only the allocation section is used. Presence of a symbol in the binary,
    # a stack dump elsewhere, or a failed build is not detection.
    allocation_section = analysis.split('PEAK MEMORY CONSUMERS')[0]
    stacks = subprocess.run(['swift', 'demangle'],
        input=(output / 'mutant/allocation-stacks.txt').read_bytes(), capture_output=True, check=True).stdout.decode()
    (output / 'mutant/allocation-stacks-demangled.txt').write_text(stacks)
    # A small error/closure allocation in the helper is insufficient. Require
    # the ten actual UInt8 sample-array allocations (five encodes per precision).
    sample_arrays = sum(int(line.rsplit(';', 1)[1]) for line in stacks.splitlines()
        if marker in line and 'SwiftJLS.OwnedImageStorage.init' in line
        and 'Swift.Array.init(repeating:' in line)
    detected = marker in allocation_section and sample_arrays == 10
    report = dict(commands=commands, detected=detected, injected_sample_array_allocations=sample_arrays,
                  source_sha256=hashlib.sha256(original.encode()).hexdigest(),
                  mutated_sha256=hashlib.sha256(mutated.encode()).hexdigest(),
                  baseline_has_injected_allocator=False,
                  mutant_consumer_passed=True,
                  mutation='One full descriptor-capacity copy into a new owner before every scalar encode; reports intentionally unchanged.',
                  scope='Allocator stack sensitivity; whole-process totals are not copy byte counts.')
    (output / 'summary.json').write_text(json.dumps(report, indent=2) + '\n')
    if not detected:
        raise RuntimeError('Allocator telemetry failed to detect the injected frame copy')
    print(json.dumps(report, indent=2))
