#!/usr/bin/env python3
"""Run two accepted video clients while continuously verifying authenticated HID."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time
p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--boot-result',type=Path,required=True);a=p.parse_args()
a.output.mkdir(parents=True,exist_ok=False)
known=Path(json.loads(a.boot_result.read_text())['run_directory'])/'known_hosts'
result={'result':'failed','hid':[]};source=None;video=None
try:
 subprocess.run(['chvt','3'],check=True)
 connector=Path('/sys/class/drm/card0-HDMI-A-2/connector_id').read_text().strip()
 with (a.output/'source.log').open('w') as log:
  source=subprocess.Popen(['gst-launch-1.0','-q','videotestsrc','is-live=true','pattern=ball','animation-mode=frames','!','video/x-raw,width=1920,height=1080,framerate=30/1','!','videoconvert','!','kmssink','connector-id='+connector,'force-modesetting=true','restore-crtc=true'],stdout=log,stderr=log)
 time.sleep(3);assert source.poll() is None
 with (a.output/'video.log').open('w') as log:
  video=subprocess.Popen([sys.executable,'lab/lan-capacity.py','--known-hosts',str(known),'--private-dir','private','--output',str(a.output/'two-clients'),'--clients','2','--seconds','120','--keep-sessions'],stdout=log,stderr=log)
 start=time.time();i=0
 while video.poll() is None:
  out=a.output/f'hid-{i:03d}';before=time.time()
  with (a.output/f'hid-{i:03d}.log').open('w') as log:
   proc=subprocess.run([sys.executable,'lab/hid-api-hil.py','--private-dir','private','--output',str(out),'--keep-session'],stdout=log,stderr=log,timeout=60)
  r=json.loads((out/'result.json').read_text());assert proc.returncode==0,r
  result['hid'].append({'start':before,'end':time.time(),'result':r['result']});i+=1
 result['video']=json.loads((a.output/'two-clients/result.json').read_text());assert video.returncode==0,result['video']
 assert time.time()-start>=120 and len(result['hid'])>=10
 result['result']='passed'
except Exception as e:result['error']=str(e)
finally:
 if video and video.poll() is None:video.terminate();video.wait(timeout=10)
 if source:source.terminate();source.wait(timeout=10)
 subprocess.run(['chvt','1'])
 (a.output/'result.json').write_text(json.dumps(result,indent=2)+'\n')
raise SystemExit(result['result']!='passed')
