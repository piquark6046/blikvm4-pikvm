#!/usr/bin/env python3
"""Final candidate preflight, lifecycle, UI and both concurrent workloads."""
import argparse,json,subprocess,sys
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--artifacts',type=Path,required=True);a=p.parse_args()
a.output.mkdir(parents=True,exist_ok=False);result={'result':'failed','passed':[]}
def run(label,args,stdin=None):
    with (a.output/(label+'.stdout')).open('w') as out,(a.output/(label+'.stderr')).open('w') as err:
        r=subprocess.run(args,input=stdin,text=True,stdout=out,stderr=err,timeout=900)
    assert r.returncode==0,label
    result['passed'].append(label)
    (a.output/'progress.json').write_text(json.dumps(result,indent=2)+'\n')
    return (a.output/(label+'.stdout')).read_text()
try:
    b=json.loads(run('boot',[sys.executable,'lab/kvmd-boot.py','--artifacts',str(a.artifacts.resolve()),'--out-root',str(Path('runs').resolve()),'--require-lab-presets']))
    known=Path(b['run_directory'])/'known_hosts';boot=a.output/'boot.stdout';result['boot']=b
    ssh=['ssh','-i','/home/user/.local/share/blikvm-m7/id_ed25519','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-o','UserKnownHostsFile='+str(known),'blikvm@192.168.88.2']
    run('inventory-source',ssh+['sudo -n tee /run/m8e-hid-inventory.py'],Path('lab/hid-inventory.py').read_text())
    run('inventory-before',ssh+['sudo -n python3 -'],Path('lab/msd-inventory.py').read_text())
    run('privilege',ssh+['sudo -n python3 -'],Path('lab/msd-privilege-inventory.py').read_text())
    run('policy',[sys.executable,'lab/lan-probe.py','--known-hosts',str(known),'--private-dir','private','--output',str(a.output/'policy')])
    run('api-lifecycle',[sys.executable,'lab/msd-hil.py','--output',str(a.output/'api-lifecycle'),'--boot-result',str(boot),'--lifecycle'])
    run('helper-negative',ssh+['sudo -n python3 -'],Path('lab/msd-helper-negative.py').read_text())
    run('msd-browser',[sys.executable,'lab/msd-browser-hil.py','--output',str(a.output/'msd-browser'),'--boot-result',str(boot)])
    for label,flags in [('two-client-storage',[]),('browser-storage',['--browser'])]:
        run(label,[sys.executable,'lab/msd-workload.py','--output',str(a.output/label),'--boot-result',str(boot),*flags])
    run('inventory-after',ssh+['sudo -n python3 -'],Path('lab/msd-inventory.py').read_text())
    result['result']='passed'
except Exception as ex:result['error']=str(ex)
(a.output/'result.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result));raise SystemExit(result['result']!='passed')
