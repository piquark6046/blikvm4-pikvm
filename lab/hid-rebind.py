#!/usr/bin/env python3
"""Software rebind through the sole frozen owner, with kvmd stopped."""
import argparse
import json
from pathlib import Path
import runpy
import subprocess
import sys
import time
H=runpy.run_path(str(Path(__file__).with_name('hid-api-hil.py')))
p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--boot-result',type=Path,required=True);a=p.parse_args()
a.output.mkdir(parents=True,exist_ok=False);rec=H['Recorder'](a.output);monitor=H['G1']['HostMonitor'](rec)
known=Path(json.loads(a.boot_result.read_text())['run_directory'])/'known_hosts'
ssh=['ssh','-i','/home/user/.local/share/blikvm-m7/id_ed25519','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-o','UserKnownHostsFile='+str(known),'blikvm@192.168.88.2']
result={'result':'failed'}
def target(label,cmd,stdin=None):
 r=subprocess.run(ssh+[cmd],input=stdin,text=True,capture_output=True,timeout=60)
 rec.save_text(label+'.stdout',r.stdout);rec.save_text(label+'.stderr',r.stderr);assert r.returncode==0,label;return r.stdout
try:
 monitor.start();before=json.loads(target('before','sudo -n python3 -',Path('lab/hid-inventory.py').read_text()))
 target('unbind','sudo -n systemctl stop kvmd && sudo -n hid-keyboard unbind')
 H['G4']['wait_device'](False,20)
 target('bind','sudo -n hid-keyboard bind && sudo -n udevadm settle --timeout=10 && sudo -n /usr/lib/kvmd-hid/resolve-hid && sudo -n systemctl start kvmd')
 H['G4']['wait_device'](True,20);time.sleep(8)
 after=json.loads(target('after','sudo -n python3 -',Path('lab/hid-inventory.py').read_text()))
 assert before['result']==after['result']=='passed';assert before['hid_mapping']==after['hid_mapping'];assert before['boot_id']==after['boot_id']
 with (a.output/'api.log').open('w') as log:
  r=subprocess.run([sys.executable,'lab/hid-api-hil.py','--private-dir','private','--output',str(a.output/'api')],stdout=log,stderr=log,timeout=60)
 assert r.returncode==0,'API after rebind';result['result']='passed'
except Exception as e:result['error']=str(e)
finally:
 monitor.stop();rec.save_text('result.json',json.dumps(result,indent=2)+'\n')
raise SystemExit(result['result']!='passed')
