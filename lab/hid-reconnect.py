#!/usr/bin/env python3
"""Fresh present/absent/present physical USB-PC gate; no target repair."""
import argparse
import json
from pathlib import Path
import runpy
import subprocess
import sys
H=runpy.run_path(str(Path(__file__).with_name('hid-api-hil.py')))
p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--boot-result',type=Path,required=True);a=p.parse_args()
a.output.mkdir(parents=True,exist_ok=False);rec=H['Recorder'](a.output)
known=Path(json.loads(a.boot_result.read_text())['run_directory'])/'known_hosts'
ssh=['ssh','-i','/home/user/.local/share/blikvm-m7/id_ed25519','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-o','UserKnownHostsFile='+str(known),'blikvm@192.168.88.2']
result={'result':'failed','manual_target_repair':False};monitor=H['G1']['HostMonitor'](rec);targetmon=None
def inventory(label):
 r=subprocess.run(ssh+['sudo -n python3 -'],input=Path('lab/hid-inventory.py').read_text(),text=True,capture_output=True,timeout=60)
 rec.save_text(label+'.json',r.stdout);rec.save_text(label+'.stderr',r.stderr)
 data=json.loads(r.stdout);assert r.returncode==0,data.get('error');return data
try:
 initial=H['G4']['wait_device'](True,20);result['before_descriptors']=H['G4']['exact_descriptors'](initial,rec,'before')
 result['usb_before']=H['usb_descriptors'](initial,rec,'before')
 before=inventory('before-inventory');monitor.start();H['G1']['host_logs'](rec,'before')
 targetmon=subprocess.Popen(ssh+['sudo -n journalctl -kf --no-pager'],stdout=(a.output/'target-live.log').open('w'),stderr=(a.output/'target-live.stderr').open('w'))
 (a.output/'ready.json').write_text(json.dumps({'ready':True,'initially_present':True}))
 print('READY TO RECONNECT USB-PC',flush=True)
 H['G4']['wait_device'](False,900);rec.save_text('disconnected.json',json.dumps({'observed':True}))
 d=H['G4']['wait_device'](True,900);result['after_descriptors']=H['G4']['exact_descriptors'](d,rec,'after')
 assert result['after_descriptors']==result['before_descriptors']
 result['usb_after']=H['usb_descriptors'](d,rec,'after')
 assert result['usb_before']==result['usb_after']
 for label,command in [
  ('api',[sys.executable,'lab/hid-api-hil.py','--private-dir','private','--output',str(a.output/'api')]),
  ('msd',[sys.executable,'lab/hid-msd-regression.py','--output',str((a.output/'msd').resolve())]),
  ('browser',[sys.executable,'lab/hid-browser-hil.py','--output',str(a.output/'browser'),'--boot-result',str(a.boot_result)])]:
  with (a.output/(label+'.log')).open('w') as log:r=subprocess.run(command,stdout=log,stderr=log,timeout=700)
  assert r.returncode==0,label
 after=inventory('after-inventory');assert before['hid_mapping']==after['hid_mapping'];assert before['boot_id']==after['boot_id']
 H['G1']['host_logs'](rec,'after');result['result']='passed'
except Exception as e:result['error']=str(e)
finally:
 if targetmon:targetmon.terminate();targetmon.wait(timeout=10)
 monitor.stop();rec.save_text('result.json',json.dumps(result,indent=2)+'\n')
print(json.dumps(result),flush=True);raise SystemExit(result['result']!='passed')
