#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
import argparse,base64,hashlib,json,pathlib
p=argparse.ArgumentParser()
for name in ['candidates','report','output']:p.add_argument('--'+name,type=pathlib.Path,required=True)
a=p.parse_args();candidates={c['name']:c for c in json.loads(a.candidates.read_text())['cases']}
report=json.loads(a.report.read_text());records=[]
for result in report['component_cases']:
 c=candidates[result['name']]
 assert result['passed'] and result['reference_maximum_error']<=c['near']
 record={key:c[key] for key in ['name','width','height','meaningfulBits','near','components','interleave','rgb']}
 record['preset']=c['preset']
 record.update(oracle=report['oracle'],successor_oracle_passed=result['passed'])
 for ext,key,value in [('jls','encoded_sha256',result['reference_encoded']),('u16le','samples_sha256',c['samples']),('decoded.u16le','decoded_sha256',result['reference_decoded_u16le'])]:
  data=base64.b64decode(value);(a.output/(c['name']+'.'+ext)).write_bytes(data);record[key]=hashlib.sha256(data).hexdigest()
 records.append(record)
(a.output/'components-reference.json').write_text(json.dumps(dict(licence='Apache-2.0 original synthetic samples',oracle=report['oracle'],archive_sha256=report['archive_sha256'],cases=records),indent=2)+'\n')
print(len(records),'published-reference component fixtures; forward candidate passes',sum(r['successor_oracle_passed'] for r in records))
