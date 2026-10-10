#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Decode successor outputs with the separately built oracle and check each sample."""
import argparse,json,pathlib,struct,subprocess,tempfile
p=argparse.ArgumentParser();p.add_argument('--oracle',type=pathlib.Path,required=True);p.add_argument('--encoded',type=pathlib.Path,required=True);p.add_argument('--fixtures',type=pathlib.Path,required=True);p.add_argument('--report',type=pathlib.Path,required=True);a=p.parse_args();records=[]
with tempfile.TemporaryDirectory(prefix='swiftjls-oracle-') as temp:
 for f in json.loads((a.fixtures/'manifest.json').read_text())['cases']:
  output=pathlib.Path(temp)/'decoded.raw';r=subprocess.run([str(a.oracle.resolve()),'decode',str(a.encoded/(f['name']+'.jls')),str(output)],capture_output=True,check=True)
  assert list(map(int,r.stdout.split()))==[f['width'],f['height'],f['meaningfulBits'],f.get('near',0)]
  source=(a.fixtures/(f['name']+'.u16le')).read_bytes();expected=struct.unpack('<'+'H'*(len(source)//2),source);raw=output.read_bytes();actual=raw if f['meaningfulBits']<=8 else struct.unpack('<'+'H'*(len(raw)//2),raw)
  error=max((abs(x-y) for x,y in zip(actual,expected)),default=0)
  assert len(actual)==len(expected) and error<=f.get('near',0),(f['name'],error)
  records.append(dict(name=f['name'],maximum_error=error,near=f.get('near',0),passed=True))
a.report.write_text(json.dumps(records,indent=2)+'\n');print(len(records),'independent sample checks passed')
