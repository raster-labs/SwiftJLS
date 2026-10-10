#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Linux file-access observation for the real in-process cross-codec consumer."""
import argparse, json, pathlib, re, subprocess
p=argparse.ArgumentParser()
p.add_argument('--binary',type=pathlib.Path,required=True)
p.add_argument('--output',type=pathlib.Path,required=True)
a=p.parse_args(); a.output.mkdir(parents=True,exist_ok=True)
command=['strace','-ff','-ttt','-s','512','-e','trace=open,openat,creat,rename,renameat,unlink,unlinkat,mkdir,mmap,write',
         '-o',str(a.output/'files.trace'),str(a.binary.resolve())]
r=subprocess.run(command,capture_output=True,timeout=120)
(a.output/'consumer.stdout').write_bytes(r.stdout);(a.output/'consumer.stderr').write_bytes(r.stderr)
assert r.returncode==0,(r.returncode,r.stderr.decode())
events=[]; boundaries={}
for file in a.output.glob('files.trace.*'):
    for line in file.read_text().splitlines():
        timestamp=re.match(r'([0-9]+\.[0-9]+) ',line)
        if not timestamp: continue
        stamp=float(timestamp[1]); events.append((stamp,line))
        marker=re.search(r'write\(2, "STORAGE_(BEGIN|END)_(12|16)\\n"',line)
        if marker: boundaries[(marker[1],int(marker[2]))]=stamp
assert len(boundaries)==4,('Missing API phase markers',boundaries)
observed=[]; prohibited=[]
for stamp,line in sorted(events):
    phase=next((bits for bits in [12,16] if boundaries[('BEGIN',bits)]<stamp<boundaries[('END',bits)]),None)
    if phase is None: continue
    if not re.search(r'\b(open|openat|creat|rename|renameat|unlink|unlinkat|mkdir)\(',line): continue
    paths=re.findall(r'"([^"\n]+)"',line)
    # Runtime/system reads are retained in the evidence, never classified as
    # image staging. Every write/create/remove or non-system open fails.
    system_read=bool(paths) and all(path.startswith(('/proc/','/sys/','/usr/lib/','/lib/','/lib64/')) for path in paths)
    writes=bool(re.search(r'O_WRONLY|O_RDWR|O_CREAT|O_TMPFILE|\b(creat|rename|renameat|unlink|unlinkat|mkdir)\(',line))
    record=dict(bits=phase,event=line,system_read=system_read)
    observed.append(record)
    if writes or not system_read: prohibited.append(record)
report=dict(command=command,exit_code=r.returncode,phase_bits=[12,16],observed_file_events=observed,
            prohibited_file_events=prohibited,passed=not prohibited,
            scope='Ordinary release consumer; kernel file syscalls during marked API routes. Not allocator/copy telemetry.')
(a.output/'summary.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
assert not prohibited, 'Application file access occurred inside the in-process route'
