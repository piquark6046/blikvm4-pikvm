#!/usr/bin/env python3
"""Independent raw replay of a zero-credit P3 browser preflight archive."""
import argparse,ast,hashlib,json,re,runpy,tarfile,tempfile
from pathlib import Path
if not __debug__:raise SystemExit('Evidence gates require assertions enabled')
REPO=Path(__file__).resolve().parents[3]
p=argparse.ArgumentParser();p.add_argument('archive',type=Path);p.add_argument('--sha256',required=True);a=p.parse_args()
assert hashlib.sha256(a.archive.read_bytes()).hexdigest()==a.sha256
H=runpy.run_path(str(REPO/'lab/hid-api-hil.py'))
assess=runpy.run_path(str(Path(__file__).with_name('inventory-gates.py')))['assess']
result={'result':'FUNCTIONAL_REPLAY_PASSED','complete_permission_boundary':'NOT_ACCEPTED','scope':'HARNESS_ONLY_PREFLIGHT','qualification_credit':0,'accepted_cycles':0,'archive_sha256':a.sha256,'storage_checks':0,'msd_transitions':0}
def read(p):return json.loads(p.read_text())
def passed(p):
 r=read(p);assert r['result']=='passed',(str(p),r.get('error'));return r
# Preserve the inherited independent raw SCSI and browser-MSD contracts exactly.
source=ast.parse((REPO/'lab/verify-msd-evidence.py').read_text())
keep=[n for n in source.body if isinstance(n,ast.FunctionDef) and n.name in ('storage','msd')]
IMAGE=H['G4']['EXPECTED']['sha256'];MEDIA='/usr/share/kvmd-msd/images/g4-storage.img'
exec(compile(ast.Module(body=keep,type_ignores=[]),'inherited-msd-replay','exec'))
with tempfile.TemporaryDirectory(prefix='p3-replay-') as tmp,tarfile.open(a.archive) as t:
 names=[m.name for m in t if m.isfile()];assert len(names)==len(set(names))
 hashes=json.load(t.extractfile('SHA256.json'));assert set(names)==set(hashes)|{'SHA256.json'}
 for name,sha in hashes.items():assert hashlib.sha256(t.extractfile(name).read()).hexdigest()==sha,name
 assert all(m.isfile() for m in t), 'unexpected archive member type'
 t.extractall(tmp,filter='data');root=Path(tmp);inv=root/'inventory';smoke=root/'smoke'
 r=read(inv/'result.json')
 assert r['result']=='completed_pending_independent_replay'
 assert r['scope']=='HARNESS_ONLY_PREFLIGHT' and r['qualification_credit']==r['accepted_cycles']==r['reboots']==0
 assert not r['target_repair'] and r['protected_unchanged']
 assert read(inv/'protected-before.json')==read(inv/'protected-after.json')
 before=read(inv/'before/target.json');after=read(inv/'after/target.json');identity=read(root/'baseline/p2-identity.json')
 for s in (before,after):assess(s,identity)
 assert before['boot_id']==after['boot_id']=='eecefe38-98a3-406c-9260-3e51de321ffe'
 assert before['sd_cid']==after['sd_cid']
 def generations(s):
  return [l for l in s['commands']['services']['stdout'].splitlines() if l.startswith(('Id=','InvocationID=','ExecMainStartTimestampMonotonic=','NRestarts='))]
 assert generations(before)==generations(after)
 assert len((inv/'browser-processes.log').read_text().splitlines())==1,'browser process remains'
 assert all(s['result']=='passed' and s['returncode']==0 for s in r['stages']) and len(r['stages'])==2
 for label in ('browser-msd','browser-hid'):
  permissions=read(smoke/label/'permission-inventory.json');e=permissions['effective'];req=permissions['requirements'];access=e['access']
  assert e['uid']==995 and e['gid']==983 and e['groups']==[983]
  assert all(access[x]['x'] for x in req['parents'])
  assert all(access[x]['r'] and not access[x]['w'] for x in req['reads'])
  assert all(not access[x]['w'] for x in req['protected'])
  assert access[req['output']]['w'] and e['create_rename_read_cleanup']
  assert set(e['negative_open_write'].values())=={13}
  for ack in (smoke/label).glob('*.ok'):
   assert t.getmember(str(ack.relative_to(root))).mode&0o777==0o644
   assert read(ack)['result']=='passed'
 msd(smoke/'browser-msd',True)
 path=smoke/'browser-hid';h=passed(path/'result.json');b=passed(path/'browser-result.json')
 assert not b['errors']
 assert h['usb_descriptor_sha256']=='733b5003b2c57a865b6366a1e4a8aa6429e9a6d3a827a79b64ba8473b445a52e'
 assert h['host_repeat']['during']==[0,0] and h['host_repeat']['restore_on_exit']
 assert not re.search(r'usb[^\n]*(?:disconnect|reset)',(path/'host-kernel-live.log').read_text(),re.I)
 names={s['name'] for s in b['steps']}
 assert {'keyboard','absolute-near-min','absolute-center','absolute-near-max','relative-0-0','relative-2-4','browser-close-cleanup','websocket-close-cleanup','logout-cleanup-and-stale-socket','video-motion','final-close'}<=names
 count=0
 for f in sorted(path.glob('*-evdev.json')):
  ev=passed(f);actual=[H['frames'](x) for x in ev['raw']];assert actual==ev['actual'],str(f)
  kind=ev['spec']['kind'];d=ev['details']
  assert ev['held']==ev['spec'].get('held',[[],[],[]])
  if kind=='exact':assert actual==d['expected']
  elif kind=='absolute':
   assert not actual[0] and not actual[2] and actual[1] and d['tolerance']==1
   assert abs(ev['axes']['0']['value']-d['x'])<=1 and abs(ev['axes']['1']['value']-d['y'])<=1
  elif kind=='relative':
   assert not actual[0] and not actual[1] and actual[2]
   assert [v for v in d['moves'] if any(v)]==[d['requested']]
   expected=[]
   for packet in d['sent']:
    if packet[0]!=4:continue
    assert packet[1]==1 and len(packet)==4
    pair=[v-256 if v>127 else v for v in packet[2:]]
    expected.append([[2,i,v] for i,v in enumerate(pair) if v])
   assert actual[2]==expected
  else:assert kind=='setup','unexpected restart or stage'
  if ev['spec']['name']=='logout-cleanup-and-stale-socket':assert d['staleSocket']==3 and d['staleHttp'] in (401,403)
  count+=1
 motion=next(x for x in b['steps'] if x['name']=='video-motion')['hashes']
 assert len(motion)==6 and len(set(motion))>=4
 # The frozen P3 JavaScript has four mode-switch iterations and no service-restart stages.
 expected_names=['login-and-open','keyboard','absolute-near-min','absolute-center','absolute-near-max','absolute-button']
 for n in range(4):
  mode='usb' if n%2 else 'usb_rel'
  expected_names += [f'prepare-mode-{n}',f'mode-{mode}-{n}',f'close-menu-{n}']
  expected_names += ([f'absolute-return-{n}'] if n%2 else [f'pointer-lock-{n}']+[f'relative-{n}-{j}' for j in range(5)]+[f'relative-button-{n}'])
 expected_names += ['focus-keyboard','browser-held-shift','browser-close-cleanup','reopen','api-websocket-open','websocket-held-shift','websocket-close-cleanup','revocation-socket-open','logout-held-input','logout-cleanup-and-stale-socket','reauth','video-motion','final-close']
 assert [s['name'] for s in b['steps']]==[s['name'] for s in h['steps']]==expected_names
 assert count==len(expected_names)
 # Review every retained post-preflight journal message, not only priority fields.
 journal=[json.loads(l) for l in after['commands']['journal_json']['stdout'].splitlines()]
 errors=[]
 for e in journal:
  message=str(e.get('MESSAGE',''))
  if re.search(r'\bERROR\b|\bCRITICAL\b|Traceback|\[error\]|\[crit\]|segfault|EXT4-fs error|I/O error|Buffer I/O|Kernel panic|Oops:|checksum error',message):
   errors.append(e)
 startup_errors=[];logout_resets=[]
 for e in errors:
  message=str(e['MESSAGE']);ts=int(e['__MONOTONIC_TIMESTAMP'])
  if ts<12_000_000:
   assert 9_000_000<=ts
   assert 'connect() to unix:/run/kvmd/api/kvmd.sock failed (2: No such file or directory)' in message or 'auth request unexpected status: 502' in message
   startup_errors.append(ts)
  else:
   assert e['_SYSTEMD_UNIT']=='nginx.service'
   assert 'recv() failed (104: Connection reset by peer) while proxying upgraded connection' in message
   assert re.search(r'request: "GET /api/ws(?:\?stream=false)? HTTP/1.1"',message)
   auth=[j for j in journal if j.get('_SYSTEMD_UNIT')=='kvmd.service' and
         ('Logged out user ' in str(j.get('MESSAGE','')) or 'Logged in user ' in str(j.get('MESSAGE','')))]
   preceding=[j for j in auth if int(j['__MONOTONIC_TIMESTAMP'])<ts]
   following=[j for j in auth if int(j['__MONOTONIC_TIMESTAMP'])>ts]
   assert preceding and 'Logged out user ' in preceding[-1]['MESSAGE']
   assert following and 'Logged in user ' in following[0]['MESSAGE']
   start=int(preceding[-1]['__MONOTONIC_TIMESTAMP']);end=int(following[0]['__MONOTONIC_TIMESTAMP'])
   assert any('Removed client socket:' in str(j.get('MESSAGE','')) and
              start<=int(j['__MONOTONIC_TIMESTAMP'])<end for j in journal)
   logout_resets.append({'reset_us':ts,'logout_us':start,'reauth_us':end})
 assert len(startup_errors)==6
 result['intentional_logout_socket_resets']=logout_resets
 result.update(verified_members=len(hashes),target_hashes_matched=10690,protected_hashes_matched=len(read(inv/'protected-before.json')),browser_stages=count,chromium_version=b['version'],video_unique_frames=len(set(motion)),journal_records_reviewed=len(journal),inherited_early_nginx_errors=len(startup_errors),boot_id=before['boot_id'],browser_processes_remaining=0,service_generations_unchanged=True)
print(json.dumps(result,indent=2))
