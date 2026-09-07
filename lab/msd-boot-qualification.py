#!/usr/bin/env python3
"""One complete M8-E clean RAM boot; all evidence is retained on failure."""
import argparse,json,subprocess,sys
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--artifacts',type=Path,required=True);a=p.parse_args()
a.output.mkdir(parents=True,exist_ok=False);result={'result':'failed'}
def run(name,args,stdin=None):
    with (a.output/(name+'.stdout')).open('w') as o,(a.output/(name+'.stderr')).open('w') as e:
        r=subprocess.run(args,input=stdin,text=True,stdout=o,stderr=e,timeout=700)
    assert r.returncode==0,name
    return (a.output/(name+'.stdout')).read_text()
try:
    b=json.loads(run('boot',[sys.executable,'lab/kvmd-boot.py','--artifacts',str(a.artifacts.resolve()),'--out-root',str(Path('runs').resolve()),'--require-lab-presets']))
    result['boot']=b;known=Path(b['run_directory'])/'known_hosts'
    ssh=['ssh','-i','/home/user/.local/share/blikvm-m7/id_ed25519','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-o','UserKnownHostsFile='+str(known),'blikvm@192.168.88.2']
    run('inventory-source',ssh+['sudo -n tee /run/m8e-hid-inventory.py'],Path('lab/hid-inventory.py').read_text())
    inv=json.loads(run('inventory',ssh+['sudo -n python3 -'],Path('lab/msd-inventory.py').read_text()));assert inv['result']=='passed',inv.get('error');result['boot_id']=inv['boot_id']
    run('privilege',ssh+['sudo -n python3 -'],Path('lab/msd-privilege-inventory.py').read_text())
    run('policy',[sys.executable,'lab/lan-probe.py','--known-hosts',str(known),'--private-dir','private','--output',str(a.output/'policy')])
    run('hid-api',[sys.executable,'lab/hid-api-hil.py','--private-dir','private','--output',str(a.output/'hid-api')])
    for name,script in [('msd-api','msd-hil.py'),('msd-browser','msd-browser-hil.py'),('hid-browser','hid-browser-hil.py')]:
        run(name,[sys.executable,'lab/'+script,'--output',str(a.output/name),'--boot-result',str(a.output/'boot.stdout')])
    run('hid-api-after',[sys.executable,'lab/hid-api-hil.py','--private-dir','private','--output',str(a.output/'hid-api-after')])
    run('helper-negative',ssh+['sudo -n python3 -'],Path('lab/msd-helper-negative.py').read_text())
    inv=json.loads(run('inventory-after',ssh+['sudo -n python3 -'],Path('lab/msd-inventory.py').read_text()));assert inv['result']=='passed',inv.get('error')
    result['result']='passed'
except Exception as ex:result['error']=str(ex)
(a.output/'result.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result));raise SystemExit(result['result']!='passed')
