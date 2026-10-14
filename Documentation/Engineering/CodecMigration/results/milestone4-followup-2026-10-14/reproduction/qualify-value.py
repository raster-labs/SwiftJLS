import subprocess,pathlib,json,os
r=pathlib.Path('work/m4-2026-10-14');records=[]
def run(cmd,label,env=None):
 with (r/(label+'.log')).open('w') as f:p=subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,env=env)
 records.append(dict(command=cmd,label=label,exit_code=p.returncode));(r/'value-qualification-commands.json').write_text(json.dumps(records,indent=2)+'\n')
 if p.returncode:raise RuntimeError(label)
 print(label+' passed',flush=True)
env=os.environ.copy();env['DEVELOPER_DIR']='/Applications/Xcode.app/Contents/Developer'
run(['python3',str(r/'apple-build-value.py')],'apple-build-value',env)
run(['python3',str(r/'apple-runtime-value.py'),'26.0'],'apple-runtime-value',env)
run(['python3',str(r/'apple-resource-value.py')],'apple-resource-value',env)
env['DEVELOPER_DIR']='/Library/Developer/CommandLineTools'
for name in ['AppleRuntimeConsumer','ResourceStress']:
 run(['swift','build','-c','release','--jobs','4','--package-path','Examples/'+name],'native-'+name+'-value',env)
run(['swift','build','-c','release','--jobs','4','--package-path','work/m4-benchmark/successor'],'benchmark-value',env)
binary=str(r/'run-tests-value/release/out/Products/Release/swiftjls-cli')
run(['python3','Scripts/test-payload-cli.py','--binary',binary,'--output',str(r/'cli-payload-value.json')],'cli-payload-value')
run(['python3','Scripts/test-cli.py','--binary',binary,'--output',str(r/'cli-process-value')],'cli-process-value')
