#!/usr/bin/env python3
"""Offline replay of M8-D host events, capacity records and five boot gates."""
import argparse
import hashlib
import json
from pathlib import Path
import runpy
import re
H=runpy.run_path(str(Path(__file__).with_name('hid-api-hil.py')))
p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
q=a.root/'qualification';result={'result':'failed','boots':[],'api_runs':0,'browser_stages':0,'video':[]}
REPORTS=['14bdd69b3b46b4e8a093865c10c75b6a9aaf85f7986f146d87a437e7f7afa476','b17306893223490b3e65f4b99477cad3380bcfcb0d3fa2ee0971fbf41e90111a','58b727cee37368e5916b515aa8cd89e3f0a570e8086d8aa868a154e6d6f87e7e']
USB='733b5003b2c57a865b6366a1e4a8aa6429e9a6d3a827a79b64ba8473b445a52e'
def read(path):return json.loads(path.read_text())
def passed(path):
 r=read(path);assert r['result']=='passed',(str(path),r.get('error'));return r
def mapping(r):
 assert r['result']=='passed';assert not r.get('hid_errors',[])
 assert sorted((x['address'],x['port']) for x in r['listeners_proc'])==[('192.168.88.2',22),('192.168.88.2',443)]
 assert r['ustreamer']['ppid']==r['kvmd_pid'] and set(map(int,r['ustreamer']['uid'].split()))!={0}
 assert '0::/system.slice/kvmd.service' in r['ustreamer']['cgroup']
 rows=r['hid_mapping'];assert [x['role'] for x in rows]==['keyboard','absolute','relative']
 assert [x['descriptor_sha256'] for x in rows]==REPORTS
 assert len({x['dev'] for x in rows})==3
 for x in rows:assert x['stable']=='/dev/kvmd-hid-'+x['role'] and x['function'].endswith('/hid.'+x['role'])
 assert r['denied_devices'];assert '30.000 (30/1)' in '\n'.join(r['logs'].values())
 return rows
def quiet_usb(path):
 log=(path/'host-kernel-live.log').read_text()
 assert not re.search(r'usb[^\n]*(?:disconnect|reset)',log,re.I),str(path)+' USB reset/disconnect'

def api(path):
 quiet_usb(path)
 r=passed(path/'result.json');assert [x['sha256'] for x in r['descriptors']]==REPORTS;assert r['usb_descriptor_sha256']==USB
 assert [x['interface'] for x in r['evdev']]==[0,1,2]
 assert set(r['checks'])=={'keyboard','absolute','relative-switch-0','absolute-switch-1','relative-switch-2','absolute-switch-3'}
 for name in r['checks']:
  ev=read(path/(name+'.json'));actual=[H['frames'](x) for x in ev['events']];assert actual==ev['actual']==ev['expected'],str(path/name)
 assert len(read(path/'keyboard.json')['actual'][0])==12
 assert len(r['authorization'])>=4 and all(x['status'] in (401,403) for x in r['authorization'])
 assert len(r['excluded_routes'])==5 and all(x['status']==404 for x in r['excluded_routes'])
 result['api_runs']+=1

def browser(path):
 quiet_usb(path)
 r=passed(path/'result.json');assert r['usb_descriptor_sha256']==USB
 assert r['host_repeat']['during']==[0,0] and r['host_repeat']['restore_on_exit']
 b=passed(path/'browser-result.json');names={x['name'] for x in b['steps']}
 assert {'browser-close-cleanup','websocket-close-cleanup','logout-cleanup-and-stale-socket','kvmd-restart-cleanup','nginx-reconnect','video-motion'}<=names
 for f in sorted(path.glob('*-evdev.json')):
  ev=passed(f);actual=[H['frames'](x) for x in ev['raw']];assert actual==ev['actual'],str(f)
  kind=ev['spec']['kind'];d=ev['details']
  assert ev['held']==ev['spec'].get('held',[[],[],[]])
  if kind=='exact':assert actual==d['expected']
  if kind=='absolute':
   assert not actual[0] and not actual[2] and actual[1]
   assert d['tolerance']==1
   assert abs(ev['axes']['0']['value']-d['x'])<=1 and abs(ev['axes']['1']['value']-d['y'])<=1
  if kind=='relative':
   assert not actual[0] and not actual[1] and actual[2]
   assert [v for v in d['moves'] if any(v)]==[d['requested']]
   expected=[]
   for packet in d['sent']:
    if packet[0]!=4:continue
    assert packet[1]==1 and len(packet)==4
    pair=[v-256 if v>127 else v for v in packet[2:]]
    expected.append([[2,i,v] for i,v in enumerate(pair) if v])
   assert actual[2]==expected
  if ev['spec']['name']=='logout-cleanup-and-stale-socket':assert d['staleSocket']==3 and d['staleHttp'] in (401,403)
  result['browser_stages']+=1
 assert len(next(x for x in b['steps'] if x['name']=='video-motion')['hashes'])==6

def video(path,count):
 r=passed(path/'result.json');assert r['seconds']==120 and r['client_count']==count
 for i,c in enumerate(r['clients']):
  frames=[json.loads(s) for s in (path/f'client-{i}/frames.jsonl').read_text().splitlines()]
  assert len(frames)==c['frames'] and len(frames)>=3240
  fps=len(frames)/c['elapsed'];assert fps>=27 and abs(fps-c['fps'])<1e-8
  assert max(b-a for a,b in zip([0]+[x['t'] for x in frames],[x['t'] for x in frames]+[120]))<=3
  for t in range(24):assert len({x['sha256'] for x in frames if t*5<=x['t']<(t+1)*5})>=2
  result['video'].append({'path':str(path.relative_to(a.root)),'client':i,'fps':fps,'frames':len(frames)})
 samples=[json.loads(s) for s in (path/'target-resources.jsonl').read_text().splitlines()]
 assert len(samples)>=50
 for s in samples:
  children=[p for p in s['processes'] if p['comm']=='ustreamer'];assert len(children)==1
  mains=[p for p in s['processes'] if p['comm'].startswith('kvmd/main')];assert len(mains)==1 and children[0]['ppid']==mains[0]['pid']
 assert max(s['streamer']['result']['stream']['clients'] for s in samples)>=count
try:
 for n in range(1,6):
  path=q/f'direct-boot{n}';r=passed(path/'result.json');before=read(path/'inventory.stdout');after=read(path/'inventory-after.stdout')
  meta=read(a.root/'runs'/r['boot']['run_id']/'metadata.json')
  assert meta['artifacts']['initramfs.cpio.gz']['sha256']=='d881f1da38c25976b2446ff62d5039e73246b8c78248ab3c4ea7588ea4c98857'
  assert meta['artifacts']['kvmd-web_4.213-1blikvm3_arm64.deb']['sha256']=='5fefaed7f8cd7202c775c7d41110e0408a0225d04621d59da29f4a6c65943788'
  assert mapping(before)==mapping(after);assert before['boot_id']==after['boot_id']==r['boot_id']
  passed(path/'policy/result.json');api(path/'api');api(path/'api-after');browser(path/'browser');passed(path/'msd/result.json')
  result['boots'].append({'number':n,'boot_id':r['boot_id'],'run_id':r['boot']['run_id'],'mapping':before['hid_mapping']})
 assert len({b['boot_id'] for b in result['boots']})==5
 passed(q/'direct-rebind/result.json');api(q/'direct-rebind/api')
 reconnect=passed(q/'direct-reconnect/result.json');assert reconnect['manual_target_repair'] is False and reconnect['usb_before']==reconnect['usb_after']==USB
 assert read(q/'direct-reconnect/ready.json')['initially_present'] and read(q/'direct-reconnect/disconnected.json')['observed']
 assert mapping(read(q/'direct-reconnect/before-inventory.json'))==mapping(read(q/'direct-reconnect/after-inventory.json'))
 api(q/'direct-reconnect/api');browser(q/'direct-reconnect/browser');passed(q/'direct-reconnect/msd/result.json')
 workload=passed(q/'direct-two-client/result.json');assert len(workload['hid'])>=10
 for p in sorted((q/'direct-two-client').glob('hid-[0-9]*')):
  if p.is_dir():api(p)
 video(q/'direct-two-client/two-clients',2)
 browser(q/'direct-browser-workload');video(q/'direct-browser-workload/concurrent-video',1)
 mapping(read(q/'direct-workloads-inventory.json'))
 result['result']='passed'
except Exception as e:result['error']=str(e)
a.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k!='boots'}));raise SystemExit(result['result']!='passed')
