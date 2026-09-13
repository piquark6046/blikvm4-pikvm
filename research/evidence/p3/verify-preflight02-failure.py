#!/usr/bin/env python3
"""Replay the stopped permission-boundary failure without awarding cycle credit."""
import argparse,hashlib,json,runpy,tarfile
from pathlib import Path
if not __debug__:raise SystemExit('Assertions must be enabled')
p=argparse.ArgumentParser();p.add_argument('first',type=Path);p.add_argument('second',type=Path);a=p.parse_args()
SHA1='c528cd34d02e0a939edd4bbb7dfec7be6e7ff5dc83854472604154e4bfea0f6f'
SHA2='be15a52352e74b222e219a0ead96f10aa523eefc26d4f4bbe266afa4fad0d644'
assess=runpy.run_path(str(Path(__file__).with_name('inventory-gates.py')))['assess']
def verify(t):
 names=[m.name for m in t if m.isfile()];assert len(names)==len(set(names))
 hashes=json.load(t.extractfile('SHA256.json'));assert set(names)==set(hashes)|{'SHA256.json'}
 for n,h in hashes.items():assert hashlib.sha256(t.extractfile(n).read()).hexdigest()==h,n
 return hashes
assert hashlib.sha256(a.first.read_bytes()).hexdigest()==SHA1
assert hashlib.sha256(a.second.read_bytes()).hexdigest()==SHA2
with tarfile.open(a.first) as first,tarfile.open(a.second) as second:
 h1=verify(first);h2=verify(second)
 def read(n):return json.load(second.extractfile(n))
 r=read('inventory/boundary-failure.json')
 assert r['result']=='FAILED' and r['reboot_cycles_consumed']==r['qualification_credit']==r['accepted_cycles']==0
 assert not r['target_repair'] and not r['second_card_written'] and r['power_cuts']==0
 assert r['controller_result']['result']=='in_progress'
 assert r['controller_unit'].startswith('ActiveState=inactive\nSubState=dead\n')
 # The service exit code does not override the controller's interrupted result.
 for name in ('browser-msd','browser-hid'):
  p='/var/lib/blikvm-p3-browser/preflight01/'+name
  entry=r['permission_inventory'][p]
  assert entry=={'uid':995,'gid':983,'mode':'0o750','effective_write':True}
 identity=read('baseline/p2-identity.json')
 before=read('inventory/before/target.json');preserved=read('inventory/boundary-preservation/target.json')
 for snapshot in (before,preserved):assess(snapshot,identity)
 assert before['boot_id']==preserved['boot_id']=='eecefe38-98a3-406c-9260-3e51de321ffe'
 assert before['sd_cid']==preserved['sd_cid']
 def generations(s):return [l for l in s['commands']['services']['stdout'].splitlines() if l.startswith(('Id=','InvocationID=','ExecMainStartTimestampMonotonic=','NRestarts='))]
 assert generations(before)==generations(preserved)
 protected=read('inventory/protected-before.json')
 assert protected==read('inventory/protected-after-boundary.json') and len(protected)==99
 live=read('inventory/previous-preflight-live-hashes.json')
 assert live=={n:h for n,h in h1.items() if n.startswith(('smoke/','inventory/'))}
 assert len(live)==482
 assert len(second.extractfile('inventory/browser-processes.log').read().splitlines())==1
 result={'phase':'P3-A attempt 02 preparation','result':'STOPPED_PREFLIGHT_FAILED',
         'attempt02_reboot_sequence':'NOT_STARTED','accepted_cycles':0,'reboot_cycles_consumed':0,
         'failure':'previous preflight evidence directories remained writable by browser uid 995',
         'first_preflight':'browser functionality replay passed; complete permission boundary not accepted',
         'second_preflight':'stopped during browser MSD; original interrupted controller record retained',
         'first_archive_sha256':SHA1,'first_verified_members':len(h1),
         'second_archive_sha256':SHA2,'second_verified_members':len(h2),
         'target_hashes_matched':10690,'target_identity_unchanged':True,
         'target_service_generations_unchanged':True,'protected_bridge_hashes_matched':99,
         'first_preflight_live_files_unchanged':482,'browser_processes_remaining':0,
         'target_repair':False,'power_cuts':0,'second_card_written':False,
         'P2':'PASSED','P3':'NOT_ACCEPTED','P3_B':'NOT_STARTED','P3_C':'NOT_STARTED',
         'M6_ATX':'DEFERRED','RO_overlay':'DEFERRED'}
 print(json.dumps(result,indent=2))
