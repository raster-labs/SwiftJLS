#!/usr/bin/env python3
"""Independent hash/privacy scan of an external candidate005 publication stage."""
import argparse,datetime,gzip,hashlib,json,pathlib,re
ap=argparse.ArgumentParser();ap.add_argument('manifest',type=pathlib.Path);ap.add_argument('--output',type=pathlib.Path,required=True);args=ap.parse_args()
base=pathlib.Path(__file__).resolve().parent
private=(base/'platform-candidate005/vm-ssh.exp').read_text();secrets=[]
for m in re.finditer(r'\bsend(?:\s+--)?\s+"((?:\\.|[^"\\])*)"',private):
 v=m.group(1).replace('\\r','').replace('\\n','')
 if len(v)>=4 and '$' not in v:secrets.append(v.encode())
assert secrets,'No literal authentication material extracted; fail closed.'
manifest=json.loads(args.manifest.read_text());parent=args.manifest.parent;root=parent/manifest['archive_id']
assert manifest['publication_mode']=='partial_checkpoint' and manifest['milestone4_complete'] is False
assert manifest['source_receipt_sha256']=='87bda184d21845362608a5a0b2198a9d6840a4324c5bdf2e8f6c5d9978e299e6'
assert manifest['host_tests']==157 and manifest['named_suites']==28 and manifest['xunit_classnames']==29
assert manifest['source_files']==39 and manifest['test_files']==32
assert manifest['production_peakWorkspaceBytes'] is None and manifest['pure_algorithm_workspace_complete'] is False
findings=[];seen=set();gz_count=0;stored_bytes=logical_bytes=0;json_values=0
sha=lambda b:hashlib.sha256(b).hexdigest()
redacted=lambda s:not s or s.startswith(('[redacted','<redacted'))
def strings(v):
 if isinstance(v,str):yield v
 elif isinstance(v,list):
  for child in v:yield from strings(child)
 elif isinstance(v,dict):
  for child in v.values():yield from strings(child)
def walk(v,path,field=()):
 if isinstance(v,dict):
  proc=('exe_name' in v and ('pid' in v or 'cpu' in v)) or ('exe' in v and 'max_ps_cpu_percent' in v)
  for k,x in v.items():
   sensitive=k in {'full_command','imageEnv'} or (k=='command' and proc)
   if sensitive and any(not redacted(s) for s in strings(x)):
    findings.append({'file':path,'kind':'unrelated_argv_or_image_environment','field':'.'.join(field+(k,))})
   walk(x,path,field+(k,))
 elif isinstance(v,list):
  for i,x in enumerate(v):walk(x,path,field+(str(i),))
for e in manifest['files']:
 rel=e['path'];p=parent/rel
 assert rel not in seen and p.resolve().is_relative_to(root.resolve());seen.add(rel)
 name=p.name
 if '.private.' in name or name in {'vm-ssh.exp','known_hosts','id_rsa','id_ed25519'} or name.endswith(('.key','.pem')):
  findings.append({'file':rel,'kind':'private_filename'})
 assert not p.is_symlink() and p.is_file()
 data=p.read_bytes();assert len(data)==e['bytes'] and sha(data)==e['sha256'],rel
 plain=gzip.decompress(data) if e.get('compression')=='gzip' else data
 gz_count+=e.get('compression')=='gzip';stored_bytes+=len(data);logical_bytes+=len(plain)
 assert len(plain)==e['uncompressed_bytes'] and sha(plain)==e['uncompressed_sha256'],rel
 if any(secret in plain for secret in secrets):findings.append({'file':rel,'kind':'private_auth_literal'})
 if re.search(rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|\bgh[pousr]_[A-Za-z0-9]{30,}\b|\bgithub_pat_[A-Za-z0-9_]{30,}\b|Bearer [A-Za-z0-9._~+/-]{20,}',plain):
  findings.append({'file':rel,'kind':'credential_pattern'})
 if not e['logical_path'].endswith('.py') and any(x in plain for x in [b'--user-data-dir=',b'--field-trial-handle=',b'--pseudonymization-salt-handle=',b'--vscode-window-config=']):
  findings.append({'file':rel,'kind':'unrelated_application_argv_marker'})
 if plain[:4] in {b'\x7fELF',b'\xcf\xfa\xed\xfe',b'\xfe\xed\xfa\xcf',b'\xca\xfe\xba\xbe'}:
  findings.append({'file':rel,'kind':'executable_binary'})
 logical=e['logical_path']
 if logical=='review/controls005-rss528_runner.py.json' and plain==b'':
  continue  # Exact retained empty stdout from failed preparation; no JSON receipt claim.
 if logical.endswith(('.json','.jsonl')):
  records=(json.loads(line) for line in plain.decode().splitlines() if line) if logical.endswith('.jsonl') else [json.loads(plain)]
  for value in records:json_values+=1;walk(value,rel)
actual={str(p.relative_to(parent)) for p in root.rglob('*') if p.is_file()};assert actual==seen
assert len(seen)==manifest['file_count'] and stored_bytes==manifest['total_compressed_bytes'] and logical_bytes==manifest['total_uncompressed_bytes']
receipt=dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),manifest=str(args.manifest),manifest_sha256=sha(args.manifest.read_bytes()),status='passed' if not findings else 'findings',files=len(seen),gzip_files=gz_count,stored_bytes=stored_bytes,logical_bytes=logical_bytes,json_records_reviewed=json_values,hashes_and_inventory_match=True,scope='All stored and decompressed logical file bytes; private native authentication literal remains local and never printed; structural unrelated process argv/imageEnv, credential patterns and binary/private-name checks.',findings=findings)
args.output.write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps({k:v for k,v in receipt.items() if k!='scope'},indent=2))
