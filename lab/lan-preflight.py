#!/usr/bin/env python3
"""Clean candidate preflight; every phase retains a distinct result file."""
import json
from pathlib import Path
import subprocess
import sys

root=Path.cwd();q=root/'qualification';here=root/'lab'

def run(name,args):
    with (q/(name+'.stderr')).open('w') as e:
        r=subprocess.run(args,stdout=subprocess.PIPE,stderr=e,text=True)
    (q/(name+'.json')).write_text(r.stdout)
    assert r.returncode==0,name
    v=json.loads(r.stdout);assert v['result']=='passed',name
    return v

boot=run('final-boot',[sys.executable,str(here/'kvmd-boot.py'),'--artifacts',str(root/'artifacts-final'),
                      '--out-root',str(root/'runs'),'--require-lab-presets'])
run('final-access',[sys.executable,str(here/'lan-probe.py'),'--known-hosts',str(Path(boot['run_directory'])/'known_hosts'),
                    '--private-dir',str(root/'private'),'--output',str(q/'final-access')])
# Repeat the full native HIL on the clean corrected image; retain all failures.
run('final-hil',[sys.executable,str(here/'web-video-hil.py'),'--boot-result',str(q/'final-boot.json'),
                 '--out-root',str(root/'runs'),'--seconds','120'])
run('final-session',[sys.executable,str(here/'lan-session.py'),'--boot-result',str(q/'final-boot.json'),
                     '--output',str(q/'final-session'),'--private-dir',str(root/'private'),
                     '--lifecycle','--single-resources','--capacity-trials','3'])
print(json.dumps({'result':'passed','boot':boot['run_id']}))
