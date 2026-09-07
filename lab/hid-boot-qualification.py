#!/usr/bin/env python3
"""One immutable clean RAM boot with policy, inventory, evdev and RO MSD gates."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--artifacts',type=Path,required=True);a=p.parse_args()
a.output.mkdir(parents=True,exist_ok=False);result={'result':'failed'}
def run(name,args,stdin=None):
 with (a.output/(name+'.stdout')).open('w') as o,(a.output/(name+'.stderr')).open('w') as e:
  r=subprocess.run(args,input=stdin,text=True,stdout=o,stderr=e,timeout=700)
 assert r.returncode==0,name
 return (a.output/(name+'.stdout')).read_text()
try:
 boot=run('boot',[sys.executable,'lab/kvmd-boot.py','--artifacts',str(a.artifacts.resolve()),'--out-root',str(Path('runs').resolve()),'--require-lab-presets'])
 b=json.loads(boot);result['boot']=b;known=Path(b['run_directory'])/'known_hosts'
 ssh=['ssh','-i','/home/user/.local/share/blikvm-m7/id_ed25519','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-o','UserKnownHostsFile='+str(known),'blikvm@192.168.88.2']
 inv=json.loads(run('inventory',ssh+['sudo -n python3 -'],Path('lab/hid-inventory.py').read_text()));assert inv['result']=='passed',inv.get('error');result['boot_id']=inv['boot_id']
 run('policy',[sys.executable,'lab/lan-probe.py','--known-hosts',str(known),'--private-dir','private','--output',str(a.output/'policy')])
 run('api',[sys.executable,'lab/hid-api-hil.py','--private-dir','private','--output',str(a.output/'api')])
 run('msd',[sys.executable,'lab/hid-msd-regression.py','--output',str((a.output/'msd').resolve())])
 # Every boot uses normal UI; optional workload is a separate gate.
 run('browser',[sys.executable,'lab/hid-browser-hil.py','--output',str(a.output/'browser'),'--boot-result',str(a.output/'boot.stdout')])
 run('api-after',[sys.executable,'lab/hid-api-hil.py','--private-dir','private','--output',str(a.output/'api-after')])
 inv=json.loads(run('inventory-after',ssh+['sudo -n python3 -'],Path('lab/hid-inventory.py').read_text()));assert inv['result']=='passed',inv.get('error')
 result['result']='passed'
except Exception as e:result['error']=str(e)
(a.output/'result.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result));raise SystemExit(result['result']!='passed')
