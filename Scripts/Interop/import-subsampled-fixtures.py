#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Import synthetic decoder-compatibility fixtures with reproducible hashes."""
import argparse,hashlib,json,pathlib,shutil
p=argparse.ArgumentParser()
for name in ['source','provenance','output']:p.add_argument('--'+name,type=pathlib.Path,required=True)
a=p.parse_args();d=json.loads((a.source/'subsampled-nonzero.json').read_text())
d['provenance']=json.loads(a.provenance.read_text());d['licence']='Apache-2.0, synthetic samples'
d['interpretation']='Pinned predecessor decoder compatibility; fixture-only encoder scheduler adapted for fixed sampling factors; not a separate standards oracle'
a.output.mkdir(parents=True,exist_ok=True)
for row in d['cases']:
 for ext in ['jls','u16le']:
  source=a.source/(row['name']+'.'+ext);shutil.copy2(source,a.output/source.name)
  row[ext+'_sha256']=hashlib.sha256(source.read_bytes()).hexdigest()
(a.output/'subsampled-nonzero.json').write_text(json.dumps(d,indent=2)+'\n')
