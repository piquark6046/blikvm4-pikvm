#!/usr/bin/env python3
"""Five consecutive clean RAM boots with unchanged direct HTTPS access policy."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True)
p.add_argument('--preflight',type=Path,required=True);a=p.parse_args();root=a.root.resolve()
preflight=json.loads(a.preflight.read_text());assert preflight['result']=='passed'
assert len(preflight['capacity'])>=3,'three explicit two-client trials required'
two=all(x['result']=='passed' for x in preflight['capacity'])
series=root/'series';series.mkdir(exist_ok=False)
HERE=Path(__file__).resolve().parent
result={'result':'failed','completed':[],'two_client_gate':two};boots=[]

def run(label,args):
    with (series/(label+'.stderr')).open('w') as e:
        r=subprocess.run(args,stdout=subprocess.PIPE,stderr=e,text=True)
    (series/(label+'.json')).write_text(r.stdout)
    assert r.returncode==0,label+' failed'
    v=json.loads(r.stdout);assert v['result']=='passed',label
    return v
try:
    for i in range(1,6):
        boot=run('boot-'+str(i),[sys.executable,str(HERE/'kvmd-boot.py'),'--artifacts',str(root/'artifacts-final'),
                 '--out-root',str(root/'runs'),'--require-lab-presets'])
        boots.append(boot);(series/'boots.jsonl').write_text(''.join(json.dumps(v)+'\n' for v in boots))
        known=str(Path(boot['run_directory'])/'known_hosts')
        run('access-'+str(i),[sys.executable,str(HERE/'lan-probe.py'),'--known-hosts',known,
             '--private-dir',str(root/'private'),'--output',str(series/('access-'+str(i)))])
        ssh=['ssh','-i','/home/user/.local/share/blikvm-m7/id_ed25519','-o','BatchMode=yes',
             '-o','StrictHostKeyChecking=yes','-o','UserKnownHostsFile='+known,'blikvm@192.168.88.2','sudo -n python3 -']
        r=subprocess.run(ssh,input=(HERE/'lan-inventory.py').read_text(),text=True,capture_output=True,timeout=60)
        (series/('startup-'+str(i)+'.json')).write_text(r.stdout)
        (series/('startup-'+str(i)+'.stderr')).write_text(r.stderr)
        assert r.returncode==0 and json.loads(r.stdout)['result']=='passed'
        run('hil-'+str(i),[sys.executable,str(HERE/'web-video-hil.py'),'--boot-result',str(series/('boot-'+str(i)+'.json')),
            '--out-root',str(root/'runs'),'--seconds','15','--boot-smoke'])
        run('session-'+str(i),[sys.executable,str(HERE/'lan-session.py'),'--boot-result',str(series/('boot-'+str(i)+'.json')),
            '--private-dir',str(root/'private'),'--output',str(series/('session-'+str(i))),
            '--capacity-trials','1' if two else '0'])
        session=json.loads((series/('session-'+str(i))/'result.json').read_text())
        if two:assert all(x['result']=='passed' for x in session['capacity']), 'accepted two-client regression'
        result['completed'].append({'index':i,'boot_id':session['before']['boot_id'],
             'single_fps':session['browser']['stream']['fps'],'capacity':session['capacity']})
        (series/'progress.json').write_text(json.dumps(result,indent=2)+'\n')
    run('five-boot-gate',[sys.executable,str(HERE/'ubuntu-reboot-gate.py'),'--series',str(series/'boots.jsonl'),
         '--runs',str(root/'runs'),'--count','5'])
    result['result']='passed'
except Exception as e:result['error']=str(e)
(series/'result.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result))
raise SystemExit(result['result']!='passed')
