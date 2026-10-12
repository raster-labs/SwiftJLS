#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Prove layout expectations fail for wrong stride/order; never edit the checkout."""
import argparse, hashlib, json, pathlib, re, shutil, subprocess, tempfile, time
p = argparse.ArgumentParser()
p.add_argument('--output', type=pathlib.Path, required=True)
p.add_argument('swift_flags', nargs=argparse.REMAINDER)
a = p.parse_args()
root = pathlib.Path(__file__).resolve().parents[2]
a.output.mkdir(parents=True, exist_ok=True)
flags = a.swift_flags[1:] if a.swift_flags[:1] == ['--'] else a.swift_flags
relative = 'Sources/SwiftJLS/JPEGLS/'
originals = {name: (root / relative / name).read_text() for name in ['ScalarCodec.swift', 'ComponentSamples.swift']}
mutants = []
def add(name, file, before, after, count, start=0, end=None):
    source = originals[file]
    region = source[start:end]
    assert region.count(before) == count, (name, region.count(before), count)
    replacement = source[:start] + region.replace(before, after) + (source[end:] if end is not None else '')
    mutants.append((name, file, replacement))
scalar = originals['ScalarCodec.swift']; boundary = scalar.index('    static func decode(')
add('scalar-encode-stride', 'ScalarCodec.swift', 'rowStride: plane.rowBytes / view.sampleBytes', 'rowStride: descriptor.width', 3, end=boundary)
add('scalar-decode-stride', 'ScalarCodec.swift', 'rowStride: plane.rowBytes / (descriptor.storageBits / 8)', 'rowStride: descriptor.width', 1, start=boundary)
add('scalar-encode-byte-order', 'ScalarCodec.swift', 'littleEndian: descriptor.byteOrder == .littleEndian', 'littleEndian: descriptor.byteOrder != .littleEndian', 1, end=boundary)
add('scalar-decode-byte-order', 'ScalarCodec.swift', 'littleEndian: descriptor.byteOrder == .littleEndian', 'littleEndian: descriptor.byteOrder != .littleEndian', 1, start=boundary)
component = originals['ComponentSamples.swift']; boundary = component.index('struct ComponentSampleWriter')
for direction, start, end, count in [('encode', 0, boundary, 1), ('decode', boundary, None, 2)]:
    add('component-' + direction + '-stride', 'ComponentSamples.swift', '(index / width) * rowBytes', '(index / width) * width * pixelStride', count, start, end)
# Flip the accessor's declared order consistently: wrong endian remains a valid,
# bounded physical access, but must not preserve logical sample values.
add('component-encode-byte-order', 'ComponentSamples.swift', 'return littleEndian ?', 'return !littleEndian ?', 1, end=boundary)
add('component-decode-byte-order', 'ComponentSamples.swift', 'littleEndian ?', '!littleEndian ?', 2, start=boundary)
report = dict(revision=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip(),
              build='ordinary release; no sanitizers', source_sha256={k: hashlib.sha256(v.encode()).hexdigest() for k,v in originals.items()}, results=[])
with tempfile.TemporaryDirectory(prefix='swiftjls-layout-mutations-') as directory:
    temporary = pathlib.Path(directory)
    for name in ['Sources', 'Tests']:
        shutil.copytree(root/name, temporary/name)
    shutil.copy2(root/'Package.swift', temporary/'Package.swift')
    def run(name):
        command = ['swift','test','-c','release','--jobs','2','--filter','StorageEvidenceTests', *flags]
        started=time.monotonic()
        log=a.output/(name+'.log')
        with log.open('w') as stream:
            r=subprocess.run(command,cwd=temporary,stdout=stream,stderr=subprocess.STDOUT,timeout=240)
        output=log.read_text()
        issues=len(re.findall(r'recorded an issue', output))
        expectations=len(re.findall(r'recorded an issue[^\n]*Expectation failed', output))
        summary=re.findall(r'Test run with .*', output)
        summary_issues=re.search(r'with (\d+) issues?', summary[-1] if summary else '')
        result=dict(summary_issue_count=int(summary_issues[1]) if summary_issues else 0, name=name,command=command,exit_code=r.returncode,seconds=round(time.monotonic()-started,2),
                    recorded_issues=issues,expectation_failures=expectations,summary=summary[-1:] or [])
        report['results'].append(result)
        (a.output/'summary.json').write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps(result),flush=True)
        assert summary, (name,'Test execution did not reach its summary')
        assert (r.returncode==0 and issues==0) if name=='baseline' else (r.returncode!=0 and issues>0), (name,'Mutation survived or failed outside test execution')
    run('baseline')
    for name,file,source in mutants:
        for clean,contents in originals.items(): (temporary/relative/clean).write_text(contents)
        (temporary/relative/file).write_text(source)
        run(name)
print('All eight layout mutations were detected by the executed tests.')
