#!/usr/bin/env python3
"""P3-A cycle 1 replay: declared reboot plus unchanged H5R2 functional gates."""
import hashlib,json,sys,tarfile
from pathlib import Path
R=Path(__file__).resolve().parents[3]
sha=lambda b:hashlib.sha256(b).hexdigest()
def verify(archive,digest):
 assert sha(archive.read_bytes())==digest
 name='p3-a02-cycle-001'
 with tarfile.open(archive) as t:
  read=lambda n:json.load(t.extractfile(n))
  c=read('controller/'+name+'/cycle.json');old=read('controller/'+name+'/preboot/target.json');start=read('controller/'+name+'/startup/target.json')
  assert c['result']=='CYCLE_PASS_PENDING_INDEPENDENT_REPLAY'
  assert c['attempt']==2 and c['cycle']==1 and c['total_cycles']==12 and c['accepted_cycles']==0
  assert not c['preparation_reboot_counted'] and c['ethernet']=='connected_throughout'
  assert read('controller/h5r2-acceptance.json')['result']=='H5R2_INDEPENDENTLY_ACCEPTED'
  assert c['before_boot_id']==old['boot_id']=='1c8365c7-90bf-46fb-8db4-5ec06a745a6a'
  assert c['startup_boot_id']==start['boot_id']!=old['boot_id']
  for k in ('sd_cid','machine_id','host_public_keys','hash_checks'):assert old[k]==start[k]
  assert not any(m.name=='controller/P3_A02_FAILED.json' for m in t)
  uart=t.extractfile('controller/'+name+'/uart/uart-001.raw').read()
  markers=['U-Boot SPL','BL31:','U-Boot 2021','/boot/boot.scr','Starting kernel','root=PARTUUID=b14b0001-01','systemd[1]']
  positions=[uart.find(s.encode()) for s in markers];assert all(p>=0 for p in positions) and positions==sorted(positions)
  assert c['firmware_markers']==dict(zip(markers,positions))
  assert uart.count(b'U-Boot SPL')==1 and b'TFTP' not in uart
  events=[json.loads(l) for l in t.extractfile('controller/'+name+'/uart/events.jsonl').read().splitlines()]
  assert events[-1]['event']=='watcher_finished' and events[-1]['segments']==1
  assert not any(e['event']=='uart_unavailable' for e in events)
  import datetime
  opened=next(e for e in events if e['event']=='uart_open')
  assert datetime.datetime.fromisoformat(opened['utc']).timestamp()*1e9<c['reboot_request_wall_ns']
  recovery=[json.loads(l) for l in t.extractfile('controller/'+name+'/recovery.jsonl').read().splitlines()]
  good=recovery[-1];assert good['trusted_https'] and good['ssh_exit']==0 and good['boot_id']==start['boot_id']
  assert good['monotonic_ns']-c['reboot_request_monotonic_ns']<180_000_000_000
  prov=read('controller/'+name+'/source-provenance.json')
  for n,h in prov['files'].items():assert sha(t.extractfile('controller/'+name+'/'+n).read())==h
 # Reuse the accepted functional replayer. Bind its expected boot to this
 # independently authenticated reboot, and its first inventory to this startup.
 source=R/'research/evidence/p3/verify-h5r2-functional.py';code=source.read_text()
 replacements={"first=read(root/'controller/target-continuity/before-first-functional/target.json')":"first=read(root/'controller'/name/'startup/target.json')", "assert before['boot_id']=='1c8365c7-90bf-46fb-8db4-5ec06a745a6a'":"assert before['boot_id']==cycle_boot", "j(gate+'target-state.json'),j(gate+'host.json'))":"j(gate+'target-state.json'),j(gate+'host.json'),expected_boot=cycle_boot)"}
 for a,b in replacements.items():assert code.count(a)==1;code=code.replace(a,b)
 g={'__file__':str(source),'__name__':'p3_a02_offline','cycle_boot':start['boot_id']};exec(compile(code,str(source),'exec'),g)
 result=g['replay'](archive,digest,name);assert result['result']=='H5R2_FUNCTIONAL_ACCEPTED'
 result.update(result='P3_A02_CYCLE_001_ACCEPTED',attempt=2,cycle=1,accepted_cycles=1,total_cycles=12,qualification_credit=1,boot_id=start['boot_id'],preparation_reboot_counted=False,p3='UNACCEPTED',p3_b_c='BLOCKED')
 return result
if __name__=='__main__':print(json.dumps(verify(Path(sys.argv[1]),sys.argv[2]),indent=2))
