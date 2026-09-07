#!/usr/bin/env python3
"""Coordinate normal Chromium UI with grabbed, stage-verified Linux evdev."""
import argparse
import contextlib
import fcntl
import struct
import json
import os
from pathlib import Path
import pwd
import runpy
import subprocess
import sys
import time
H=runpy.run_path(str(Path(__file__).with_name('hid-api-hil.py')))
G4,G2=H['G4'],H['G2']
p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--boot-result',type=Path,required=True);p.add_argument('--workload',action='store_true');a=p.parse_args()
a.output.mkdir(parents=True,exist_ok=False)
for f in Path(__file__).parent.glob('hid-*'):
 if f.is_file(): (a.output/('source-'+f.name)).write_bytes(f.read_bytes())
user=pwd.getpwnam('user');os.chown(a.output,user.pw_uid,user.pw_gid)
boot=json.loads(a.boot_result.read_text());known=Path(boot['run_directory'])/'known_hosts'
ssh=['ssh','-i','/home/user/.local/share/blikvm-m7/id_ed25519','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-o','UserKnownHostsFile='+str(known),'blikvm@192.168.88.2']
rec=H['Recorder'](a.output);client=H['Client'](Path('private').resolve());monitor=H['G1']['HostMonitor'](rec)
result={'result':'failed','steps':[]};source=None;browser=None;video=None
try:
 device=G4['wait_device'](True,20);result['descriptors']=G4['exact_descriptors'](device,rec,'browser')
 result['usb_descriptor_sha256']=H['usb_descriptors'](device,rec,'browser')
 monitor.start()
 subprocess.run(['chvt','3'],check=True)
 connector=Path('/sys/class/drm/card0-HDMI-A-2/connector_id').read_text().strip()
 log=(a.output/'source.log').open('w')
 source=subprocess.Popen(['gst-launch-1.0','-q','videotestsrc','is-live=true','pattern=ball','animation-mode=frames','!','video/x-raw,width=1920,height=1080,framerate=30/1','!','videoconvert','!','kmssink','connector-id='+connector,'force-modesetting=true','restore-crtc=true'],stdout=log,stderr=log)
 time.sleep(3);assert source.poll() is None
 with contextlib.ExitStack() as stack:
  caps=[stack.enter_context(G4['Capture'](device,rec,i)) for i in range(3)]
  repeat=fcntl.ioctl(caps[0].fd,0x80084503,bytes(8))
  fcntl.ioctl(caps[0].fd,0x40084503,struct.pack('II',0,0))
  stack.callback(lambda: fcntl.ioctl(caps[0].fd,0x40084503,repeat))
  result['host_repeat']={'original':list(struct.unpack('II',repeat)),'during':[0,0],'restore_on_exit':True}
  def cleanup():
   if browser and browser.poll() is None:browser.terminate();browser.wait(timeout=10)
   client.login();client.clear();H['released'](caps)
  stack.callback(cleanup)
  client.login();client.clear();client.request('/hid/set_params',{'mouse_output':'usb'});client.request('/hid/events/send_mouse_move',{'to_x':-32768,'to_y':-32768});time.sleep(.3)
  for c in caps:H['drain'](c)
  env=dict(os.environ,NODE_EXTRA_CA_CERTS=str(Path('private/ca.crt').resolve()),PLAYWRIGHT_HOST_PLATFORM_OVERRIDE='ubuntu24.04-x64',PLAYWRIGHT_BROWSERS_PATH=str(Path('out/kvmd-web/browser/browsers').resolve()))
  log=(a.output/'browser.log').open('w')
  browser=subprocess.Popen(['runuser','-u','user','--','env',*[k+'='+env[k] for k in ('NODE_EXTRA_CA_CERTS','PLAYWRIGHT_HOST_PLATFORM_OVERRIDE','PLAYWRIGHT_BROWSERS_PATH')],'xvfb-run','-a','-s','-screen 0 1600x1200x24 -nolisten tcp','node','lab/hid-browser.mjs',str(Path('private').resolve()),str(a.output.resolve()),'workload' if a.workload else 'functional'],stdout=log,stderr=log)
  index=1;deadline=time.monotonic()+600
  while browser.poll() is None:
   assert time.monotonic()<deadline,'browser overall timeout'
   stem=a.output/f'{index:03d}';ready=stem.with_suffix('.ready')
   if not ready.exists():time.sleep(.03);continue
   spec=json.loads(ready.read_text());before=[H['drain'](c) for c in caps]
   restart=None
   if a.workload and spec['name']=='prepare-mode-0':
    video=subprocess.Popen([sys.executable,'lab/lan-capacity.py','--known-hosts',str(known),'--private-dir','private','--output',str(a.output/'concurrent-video'),'--clients','1','--seconds','120','--keep-sessions'],stdout=(a.output/'concurrent-video.log').open('w'),stderr=subprocess.STDOUT)
   if video and spec['name']=='focus-keyboard':
    video.wait(timeout=30)
    result['concurrent_video']=json.loads((a.output/'concurrent-video/result.json').read_text())
    assert video.returncode==0,result['concurrent_video']
   if spec['kind']=='restart':
    restart=subprocess.run(ssh+['sudo -n systemctl restart '+spec['service']+' && systemctl is-active '+spec['service']],capture_output=True,text=True,timeout=45)
    assert restart.returncode==0,restart.stderr
    time.sleep(2)
   stem.with_suffix('.go').write_text('go')
   end=time.monotonic()+60
   while not stem.with_suffix('.done').exists():
    assert browser.poll() is None,'browser failed before done: '+spec['name']
    assert time.monotonic()<end,'stage timeout: '+spec['name']
    time.sleep(.03)
   details=json.loads(stem.with_suffix('.done').read_text());raw=[H['drain'](c) for c in caps];actual=[H['frames'](r) for r in raw]
   check={'result':'failed','spec':spec,'details':details,'actual':actual,'raw':raw,'before':before}
   try:
    if spec['kind']=='exact':assert actual==details['expected'],actual
    elif spec['kind']=='absolute':
     assert not actual[0] and not actual[2],actual
     triples=[t for f in actual[1] for t in f];assert triples and all(t[0]==3 and t[1] in (0,1) for t in triples),triples
     axes=G2['mouse_caps'](caps[1].fd)['axes']
     assert abs(axes['0']['value']-details['x'])<=details['tolerance'],axes
     assert abs(axes['1']['value']-details['y'])<=details['tolerance'],axes
     check['axes']=axes
    elif spec['kind']=='relative':
     assert not actual[0] and not actual[1],actual
     expected=[];wire=[]
     for packet in details['sent']:
      if packet[0]!=4:continue
      deltas=[tuple(v-256 if v>127 else v for v in packet[i:i+2]) for i in range(2,len(packet),2)]
      wire.extend(deltas)
      reports=[]
      if packet[1]:
       prev=(0,0)
       for cur in deltas:
        if abs(prev[0]+cur[0])>127 or abs(prev[1]+cur[1])>127:reports.append(prev);prev=cur
        else:prev=(prev[0]+cur[0],prev[1]+cur[1])
       if any(prev):reports.append(prev)
      else:reports=deltas
      expected.extend([[[2,i,v] for i,v in enumerate(pair) if v] for pair in reports if any(pair)])
     observed=[tuple(max(-127,min(127,v)) for v in pair) for pair in details['moves'] if any(pair)]
     assert wire==observed,(wire,observed)
     assert expected and actual[2]==expected,(actual,expected)
    elif spec['kind']=='restart':
     if spec['service']=='kvmd':
      assert actual[0]==[[[1,42,0]]],actual
      triples=[t for f in actual[1] for t in f]
      assert [1,272,0] in triples and all(t==[1,272,0] or t in ([3,0,0],[3,1,0]) for t in triples),actual
      assert not actual[2],actual
     else:assert actual==[[],[],[]],actual
    held=[G2['bits'](G2['ioctl_read'](c.fd,0x18,96)) for c in caps]
    assert held==spec.get('held',[[],[],[]]),held
    check['held']=held;check['result']='passed'
   except Exception as e:check['error']=str(e)
   rec.save_text(stem.name+'-evdev.json',json.dumps(check,indent=2))
   stem.with_suffix('.ok.tmp').write_text(json.dumps({'result':check['result'],'error':check.get('error')}))
   stem.with_suffix('.ok.tmp').rename(stem.with_suffix('.ok'))
   result['steps'].append({'index':index,'name':spec['name'],'result':check['result']})
   assert check['result']=='passed',spec['name']+': '+check.get('error','')
   index+=1
  result['browser']=json.loads((a.output/'browser-result.json').read_text());assert browser.returncode==0,result['browser'].get('error')
  result['result']='passed'
except Exception as e:result['error']=str(e)
finally:
 if video and video.poll() is None:video.terminate();video.wait(timeout=10)
 if browser and browser.poll() is None:browser.terminate();browser.wait(timeout=10)
 if source:source.terminate();source.wait(timeout=10)
 subprocess.run(['chvt','1'])
 monitor.stop();rec.save_text('result.json',json.dumps(result,indent=2)+'\n')
print(json.dumps(result));raise SystemExit(result['result']!='passed')
