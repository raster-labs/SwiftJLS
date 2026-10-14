#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Summarise explicitly bounded Massif snapshots without inventing exact peaks."""
import argparse, pathlib, re, json, hashlib

def snapshots(path):
    text=path.read_text(); results=[]
    for block in re.split(r'(?m)^snapshot=\d+\n', text)[1:]:
        values={k:int(v) for k,v in re.findall(r'(?m)^(time|mem_heap_B|mem_heap_extra_B|mem_stacks_B)=(\d+)$',block)}
        if len(values)!=4: raise ValueError('Incomplete Massif snapshot')
        results.append(values)
    if not results: raise ValueError('Missing Massif snapshots')
    return results

p=argparse.ArgumentParser();p.add_argument('--directory',type=pathlib.Path,required=True);p.add_argument('--revision',required=True);a=p.parse_args()
begin=snapshots(a.directory/'massif-begin.out');end=snapshots(a.directory/'massif-end.out')
if len(begin)!=1 or len(end)!=1 or begin[0]['time']>=end[0]['time']:raise ValueError('Invalid phase markers')
inside=[s for s in snapshots(a.directory/'massif.out') if begin[0]['time']<=s['time']<=end[0]['time']]
selected=[begin[0],*inside,end[0]]
result=dict(revision=a.revision,begin=begin[0],end=end[0],interior_snapshots=len(inside),
    observation_scope='interior_and_boundaries' if inside else 'boundaries_only_no_interior_coverage',
    observed_peak_requested_heap_bytes=max(s['mem_heap_B'] for s in selected),
    observed_peak_stack_bytes=max(s['mem_stacks_B'] for s in selected),
    observed_peak_modelled_heap_overhead_bytes=max(s['mem_heap_extra_B'] for s in selected),
    observed_peak_combined_bytes=max(sum(s[k] for k in ['mem_heap_B','mem_heap_extra_B','mem_stacks_B']) for s in selected),
    profiles={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in a.directory.glob('massif*.out')},
    limitations=['Snapshot maxima are observed peaks, not exhaustive per-operation high-water guarantees.',
        'Stack bytes include runtime and marker activity on all threads; they are not isolated codec stack usage.',
        'Heap-extra bytes use the Massif allocator model, not measured host allocator overhead.',
        'Stack profiling uses dynamic instrumentation and is separate from ordinary-release Heaptrack evidence and timing.',
        'Unknown production workspace reports remain unknown; unrelated category peaks must not be added.'])
if not inside:
    result['limitations'].append('This short operation has boundary snapshots only. Transient interior peaks were not observed and remain unknown.')
if result['observed_peak_stack_bytes']<=0:raise ValueError('Stack observation missing')
(a.directory/'stack-summary.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k.startswith('observed_') or k=='interior_snapshots'}))
