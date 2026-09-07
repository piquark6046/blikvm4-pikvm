#!/usr/bin/env python3
"""Five consecutive complete clean-boot gates; stop and preserve any failure."""
import argparse,json,subprocess,sys
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--artifacts',type=Path,required=True);a=p.parse_args()
a.output.mkdir(parents=True,exist_ok=False)
r={'result':'failed','boots':[]}
try:
    for n in range(1,6):
        directory=a.output/('boot'+str(n))
        with (a.output/('boot'+str(n)+'.log')).open('w') as log:
            proc=subprocess.run([sys.executable,'lab/msd-boot-qualification.py','--output',str(directory),'--artifacts',str(a.artifacts)],stdout=log,stderr=log,timeout=1800)
        b=json.loads((directory/'result.json').read_text());r['boots'].append(b)
        (a.output/'progress.json').write_text(json.dumps(r,indent=2)+'\n')
        assert proc.returncode==0 and b['result']=='passed',(n,b.get('error'))
    assert len({b['boot_id'] for b in r['boots']})==5
    r['result']='passed'
except Exception as ex:r['error']=str(ex)
(a.output/'result.json').write_text(json.dumps(r,indent=2)+'\n')
print(json.dumps(r));raise SystemExit(r['result']!='passed')
