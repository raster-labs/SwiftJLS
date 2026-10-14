#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Collect the marked workspace matrix; preserve every command and profile."""
import argparse, json, pathlib, subprocess
p=argparse.ArgumentParser()
p.add_argument('--binary', required=True)
p.add_argument('--output', type=pathlib.Path, required=True)
p.add_argument('--revision', required=True)
a=p.parse_args();a.output.mkdir(parents=True, exist_ok=True)
cases=[]
for size in [17,512]:
    for components in [1,3]:
        for near in [0,3]:
            for operation in ['encode','owned','into','inspect']:
                cases.append((f'{size}-{components}-{near}-{operation}',[operation,str(size),str(size),str(components),str(near)]))
for profile,components,near in [('line',3,0),('line',3,3),('planar',3,0),('planar',3,3),('p16',1,0),('p16',3,3),('preset',1,3),('preset',3,0),('restart',3,3),('hp1',3,0),('hp2',3,0),('hp3',3,0)]:
    for operation in ['encode','owned','into','inspect']:
        cases.append((f'{profile}-{components}-{near}-{operation}',[operation,'257','129',str(components),str(near),profile]))
for name in ['subsampled-zero-n0','map-p16-c3-i0-w1-n0','extended-p12-65537x2']:
    for operation in ['owned','into','inspect']:
        cases.append((f'{name}-{operation}',[operation,'--fixture',f'Tests/SwiftJLSTests/Fixtures/{name}.jls']))
(a.output/'matrix.json').write_text(json.dumps(dict(revision=a.revision,cases=cases),indent=2)+'\n')
for name,args in cases:
    output=a.output/name
    subprocess.run(['python3','Scripts/StorageEvidence/trace-heap.py','--binary',a.binary,'--output',str(output),'--scope','One marked operation; setup retained and verification after the end marker','--',*args],check=True,stdout=subprocess.DEVNULL)
    subprocess.run(['python3','Scripts/StorageEvidence/measure-operation.py','--profile',str(output/'allocations.gz'),'--output',str(output/'operation.json'),'--revision',a.revision],check=True)
    print(name+' passed',flush=True)
