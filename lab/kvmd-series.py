#!/usr/bin/env python3
"""Five bounded M8-A clean boots: two full HIL runs, then three boot regressions."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

HERE=Path(__file__).resolve().parent
p=argparse.ArgumentParser()
p.add_argument('--root',type=Path,required=True)
a=p.parse_args(); root=a.root.resolve()
series=root/'qualification';series.mkdir(exist_ok=False)
boots=[];hils=[]
def run(name,args):
    with (series/(name+'.stderr')).open('w') as err:
        proc=subprocess.run(args,stdout=subprocess.PIPE,stderr=err,text=True)
    (series/(name+'.json')).write_text(proc.stdout)
    if proc.returncode: raise RuntimeError(name+' failed; see preserved evidence')
    return json.loads(proc.stdout)
for i in range(5):
    boot=run(f'boot-{i+1}',[sys.executable,str(HERE/'kvmd-boot.py'),'--artifacts',str(root/'artifacts'),
                         '--out-root',str(root/'runs'),'--require-lab-presets','--boots','1'])
    assert boot['result']=='passed';boots.append(boot)
    (series/'boots.jsonl').write_text(''.join(json.dumps(v)+'\n' for v in boots))
    args=[sys.executable,str(HERE/'kvmd-hil.py'),'--boot-result',str(series/f'boot-{i+1}.json'),
          '--out-root',str(root/'runs'),'--seconds','120']
    if i>=2: args+=['--boot-smoke']
    hil=run(f'hil-{i+1}',args);assert hil['result']=='passed';hils.append(hil)
    (series/'hils.jsonl').write_text(''.join(json.dumps(v)+'\n' for v in hils))
    if i==1:
        run('full-hil-gate',[sys.executable,str(HERE/'kvmd-gate.py'),*[v['run_directory'] for v in hils]])
        run('two-boot-gate',[sys.executable,str(HERE/'ubuntu-reboot-gate.py'),'--series',str(series/'boots.jsonl'),
                             '--runs',str(root/'runs'),'--count','2'])
    print(json.dumps({'completed_boot':i+1,'boot':boot['run_id'],'hil':hil['run_id']}),flush=True)
run('five-boot-gate',[sys.executable,str(HERE/'ubuntu-reboot-gate.py'),'--series',str(series/'boots.jsonl'),
                      '--runs',str(root/'runs'),'--count','5'])
