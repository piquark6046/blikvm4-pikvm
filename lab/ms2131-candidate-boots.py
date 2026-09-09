#!/usr/bin/env python3
"""Repeat five accepted M8-E boot gates with candidate-aware artifact publication."""
import argparse
import os
import pwd
import hashlib
import json
from pathlib import Path
import subprocess
import sys

p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--artifacts',type=Path,required=True);a=p.parse_args()
a.output.mkdir(parents=True,exist_ok=False)
browser=pwd.getpwnam('user');os.chown(a.output,browser.pw_uid,browser.pw_gid);os.chmod(a.output,0o700);os.umask(0o022)
source=Path('lab/msd-boot-qualification.py').read_text()
assert source.count("'lab/kvmd-boot.py'")==1
runner=source.replace("'lab/kvmd-boot.py'","'lab/uvc-diag-boot.py'")
path=a.output/'boot-runner.py';path.write_text(runner)
(a.output/'source-msd-boot-qualification.py').write_text(source)
r={'result':'failed','qualification':'NOT_RUN','candidate_only':True,'boots':[],
   'original_runner_sha256':hashlib.sha256(source.encode()).hexdigest(),
   'candidate_runner_sha256':hashlib.sha256(runner.encode()).hexdigest()}
try:
    for n in range(1,6):
        directory=a.output/('boot'+str(n))
        with (a.output/('boot'+str(n)+'.log')).open('w') as log:
            proc=subprocess.run([sys.executable,str(path),'--output',str(directory),'--artifacts',str(a.artifacts)],stdout=log,stderr=log,timeout=700)
        b=json.loads((directory/'result.json').read_text());r['boots'].append(b)
        (a.output/'progress.json').write_text(json.dumps(r,indent=2)+'\n')
        assert proc.returncode==0 and b['result']=='passed',(n,b.get('error'))
    assert len({b['boot_id'] for b in r['boots']})==5
    r['result']='passed'
except Exception as ex:r['error']=str(ex)
(a.output/'result.json').write_text(json.dumps(r,indent=2)+'\n')
print(json.dumps(r));raise SystemExit(r['result']!='passed')
