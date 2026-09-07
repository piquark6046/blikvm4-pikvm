#!/usr/bin/env python3
"""Recover a lost controller pipe using a completed immutable HIL result.

No reboot or service repair is allowed before the current boot's remaining
browser/capacity checks. Earlier results are retained; the boot audit still
requires five consecutive clean boots with no intervening attempt.
"""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys

p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True)
p.add_argument('--hil-result',type=Path,required=True);a=p.parse_args();root=a.root.resolve();s=root/'series';here=root/'lab'
progress=json.loads((s/'progress.json').read_text());completed=progress['completed']
assert [x['index'] for x in completed]==list(range(1,len(completed)+1))
index=len(completed)+1;assert 1<=index<=5 and not (s/'result.json').exists()
boot=json.loads((s/f'boot-{index}.json').read_text());startup=json.loads((s/f'startup-{index}.json').read_text())
hil=json.loads(a.hil_result.read_text())
assert hil['result']=='passed' and hil['boot_run']==boot['run_id'] and hil['boot_id']==startup['boot_id']
assert not (s/f'hil-{index}.json').exists()

def ssh(b):
    return ['ssh','-i','/home/user/.local/share/blikvm-m7/id_ed25519','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes',
            '-o','UserKnownHostsFile='+str(Path(b['run_directory'])/'known_hosts'),'blikvm@192.168.88.2']
current=subprocess.check_output(ssh(boot)+['cat /proc/sys/kernel/random/boot_id'],text=True).strip()
assert current==startup['boot_id'],'target rebooted since interruption'
(s/'controller-recovery.json').write_text(json.dumps({'reason':'controller interrupted; HIL stdout pipe closed after successful immutable result',
    'index':index,'boot_id':current,'hil_source':str(a.hil_result),'target_repaired':False,'additional_reboot':False},indent=2)+'\n')
shutil.copyfile(a.hil_result,s/f'hil-{index}.json')
result={'result':'failed','completed':completed,'two_client_gate':progress['two_client_gate']}
assert result['two_client_gate']

def run(label,argv):
    assert not (s/(label+'.json')).exists(),label+' already exists'
    with (s/(label+'.stderr')).open('w') as e:
        p=subprocess.run(argv,stdout=subprocess.PIPE,stderr=e,text=True)
    (s/(label+'.json')).write_text(p.stdout)
    assert p.returncode==0,label
    r=json.loads(p.stdout);assert r['result']=='passed',label
    return r
try:
    for i in range(index,6):
        if i!=index:
            boot=run(f'boot-{i}',[sys.executable,str(here/'kvmd-boot.py'),'--artifacts',str(root/'artifacts-final'),
                     '--out-root',str(root/'runs'),'--require-lab-presets'])
            with (s/'boots.jsonl').open('a') as f:f.write(json.dumps(boot)+'\n')
            run(f'access-{i}',[sys.executable,str(here/'lan-probe.py'),'--known-hosts',str(Path(boot['run_directory'])/'known_hosts'),
                '--private-dir',str(root/'private'),'--output',str(s/f'access-{i}')])
            p=subprocess.run(ssh(boot)+['sudo -n python3 -'],input=(here/'lan-inventory.py').read_text(),text=True,capture_output=True,timeout=60)
            (s/f'startup-{i}.json').write_text(p.stdout);(s/f'startup-{i}.stderr').write_text(p.stderr)
            assert p.returncode==0 and json.loads(p.stdout)['result']=='passed'
            run(f'hil-{i}',[sys.executable,str(here/'web-video-hil.py'),'--boot-result',str(s/f'boot-{i}.json'),
                '--out-root',str(root/'runs'),'--seconds','15','--boot-smoke'])
        run(f'session-{i}',[sys.executable,str(here/'lan-session.py'),'--boot-result',str(s/f'boot-{i}.json'),
            '--private-dir',str(root/'private'),'--output',str(s/f'session-{i}'),'--capacity-trials','1'])
        session=json.loads((s/f'session-{i}/result.json').read_text())
        assert all(x['result']=='passed' for x in session['capacity'])
        result['completed'].append({'index':i,'boot_id':session['before']['boot_id'],'single_fps':session['browser']['stream']['fps'],
                                    'capacity':session['capacity']})
        (s/'progress.json').write_text(json.dumps(result,indent=2)+'\n')
    run('five-boot-gate',[sys.executable,str(here/'ubuntu-reboot-gate.py'),'--series',str(s/'boots.jsonl'),
         '--runs',str(root/'runs'),'--count','5'])
    result['result']='passed'
except Exception as e:result['error']=str(e)
(s/'result.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result))
raise SystemExit(result['result']!='passed')
