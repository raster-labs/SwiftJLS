"""Pre-data amendment only: 1032 fixed short rounds. No benchmark or live preflight."""
import ast,hashlib,json,pathlib,re,shutil,subprocess
ROOT=pathlib.Path('/Users/pushparaj/projects/SwiftJLS-audit/m4-20261024')
OLD=ROOT/'campaigns005';NEW=ROOT/'campaigns005-confirmation'
PYTHON='/Users/pushparaj/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3'
sha=lambda p:hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
assert sha(OLD/'campaign-freeze.json')=='2d5d59d6a35c6c1e212b6bc5119b0bb4e9a2ff3fcc48ffb334ba88a04b653309'
oldfreeze=json.loads((OLD/'campaign-freeze.json').read_text());assert not NEW.exists()
NEW.mkdir()
for n,h in oldfreeze['files'].items():
 assert sha(OLD/n)==h,n
 if n in ['short516_runner.py','short516_analyse.py','schedules/short516-3arms-005.json']:continue
 dst=NEW/n;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(OLD/n,dst)
# Simultaneous token-boundary replacements avoid cascading counts and never touch embedded source hashes.
changes={516:1032,86:172,172:344,258:516,9288:18576,2580:5160,43:86,42:85}
for oldname,newname in [('short516_runner.py','short1032_runner.py'),('short516_analyse.py','short1032_analyse.py')]:
 source=(OLD/oldname).read_text()
 source=re.sub(r'\b(516|86|172|258|9288|2580|43|42)\b',lambda m:str(changes[int(m.group())]),source)
 source=source.replace('short516','short1032').replace('9,288','18,576').replace('6x86=1032','6x172=1032')
 compile(source,str(NEW/newname),'exec');(NEW/newname).write_text(source)
# Larger source/identity/fidelity/statistics unchanged. Its deterministic schedule embeds its local plan path.
subprocess.run([PYTHON,str(NEW/'short1032_runner.py'),'--prepare'],check=True)
subprocess.run([PYTHON,str(NEW/'larger15_runner.py'),'--prepare'],check=True)
# RSS plan does not contain a package-local path and must remain byte-identical.
assert sha(NEW/'schedules/rss528-4arms-005.json')==sha(OLD/'schedules/rss528-4arms-005.json')
protocol={'status':'pre-data amendment; no candidate005 measurement launched','root_confirmation':'Only20-second host preflight occurred before amendment; no runner launched','source_and_binaries_unchanged':True,'prior516_package':str(OLD),'prior516_freeze_sha256':sha(OLD/'campaign-freeze.json'),'reason':'Prior candidate004 decode CI half-width about0.067; doubling rounds heuristically projects about0.047. Historical planning heuristic only, not guaranteed precision. Decision precedes all candidate005 timing outputs.','fixed_short_rounds':1032,'order_strata':6,'rounds_per_stratum':172,'expected_processes':18576,'warmups':5,'observations':5,'family_size':48,'resamples':50000,'seed':20261022,'threshold':1.05,'larger_processes':120,'rss_blocks':528,'rss_processes':2112,'stop_rule':'Complete this fixed campaign once; no interim outcome look, optional extension, changed gate or automatic repeat. Preserve any stopped evidence.','host_scope':'Shared services remain running; unchanged guard and fresh root-reviewed preflight required'}
(NEW/'protocol-amendment.json').write_text(json.dumps(protocol,indent=2)+'\n')
files={str(p.relative_to(NEW)):sha(p) for p in sorted(NEW.rglob('*')) if p.is_file() and '__pycache__' not in p.parts}
f=dict(oldfreeze,files=files,preparation_script_sha256=sha(__file__),amendment='fixed1032 pre-data; original516 retained unexecuted',prior_package_freeze_sha256=sha(OLD/'campaign-freeze.json'))
(NEW/'campaign-freeze.json').write_text(json.dumps(f,indent=2)+'\n')
print('FREEZE',sha(NEW/'campaign-freeze.json'))
