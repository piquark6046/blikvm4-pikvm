#!/usr/bin/env python3
"""Independent immutable P3-S0 boot-invariant replay. No hardware operations."""
import hashlib,json,re,runpy,tarfile
from pathlib import Path
R=Path(__file__).resolve().parents[3]
sha=lambda b:hashlib.sha256(b).hexdigest()
def verify():
 c=json.loads(Path(__file__).with_name('s0-boot-invariant.json').read_text())
 p=R/'out/p3-s0/preparation-reboot.tar.gz';digest='0032c9ad2c35269e6fdadf0ca158d5167d007866318bffc2c6aa493047cf59fa'
 assert sha(p.read_bytes())==digest
 with tarfile.open(p) as t:
  data=lambda n:t.extractfile('snapshot/'+n).read()
  read=lambda n:json.loads(data(n))
  idx=read('FINAL-SHA256.json');names=[m.name for m in t if m.isfile()]
  assert len(names)==len(set(names)) and set(idx)=={n.removeprefix('snapshot/') for n in names}-{'FINAL-SHA256.json'}
  for n,h in idx.items():assert sha(data(n))==h,n
  assert sha(data('boot-invariant.json'))=='9cf77f9c6931c383657cbe625c2f640ba77da0ccf7c851b986d056e51280d899'
  assert read('boot-invariant.json')==c
  assert read('vm-current-replay.json')['result']=='S0_CURRENT_EMPTY_VERIFIED'
  events=[json.loads(l) for l in data('preparation-reboot-uart/events.jsonl').splitlines()]
  assert events[-1]['event']=='watcher_finished' and events[-1]['segments']==1
  request=read('REBOOT_REQUESTED.json');assert request['qualification_credit']==request['accepted_cycles']==0
  import datetime
  opened=next(e for e in events if e['event']=='uart_open')
  assert datetime.datetime.fromisoformat(opened['utc']).timestamp()*1e9<request['wall_ns']
  uart=data('preparation-reboot-uart/uart-001.raw').decode(errors='replace')
  for s in ('U-Boot SPL','U-Boot 2021.10','Starting kernel','Linux version'):assert uart.count(s)==1,s
  assert 'TFTP' not in uart and 'root=PARTUUID=b14b0001-01' in uart
  original=read('current-empty-complete/inventory/target.json');first=None;journals=0
  identity=json.loads((R/'out/p3/preparation/p2-identity.json').read_text())
  assess=runpy.run_path(str(Path(__file__).with_name('inventory-gates.py')))['assess']
  for phase in ('fresh-boot','after-ro-check'):
   r=read(phase+'/inventory/target.json');e=read(phase+'/target-extra.json');assess(r,identity)
   assert r['boot_id']!=original['boot_id'] and r['boot_id']==e['boot_id']
   if first is None:first=r
   else:
    assert r['boot_id']==first['boot_id']
    def gen(x):return [l for k in ('services','ssh_show') for l in x['commands'][k]['stdout'].splitlines() if l.startswith(('Id=','InvocationID=','ExecMainStartTimestampMonotonic=','NRestarts='))]
    assert gen(r)==gen(first)
   for k in ('hash_checks','sd_cid','machine_id','host_public_keys'):assert r[k]==original[k]
   assert set(k for k,v in e['gadget'].items() if k.startswith('blikvm_m5/functions/mass_storage.g4/lun.') and v.get('directory'))=={'blikvm_m5/functions/mass_storage.g4/lun.0'}
   for k in ('file','ro','cdrom','removable','nofua','inquiry_string'):
    assert bytes.fromhex(e['gadget']['blikvm_m5/functions/mass_storage.g4/lun.0/'+k]['hex']).decode().strip()==c[k]
   api=json.loads(e['commands']['api']['stdout'])['result']
   assert api['drive']['connected'] and not api['drive']['rw'] and not api['drive']['cdrom']
   assert api['drive']['image']['name']==c['api_image'] and api['online'] and not api['busy']
   h=read(phase+'/host-media-hash.json');assert h['returncode']==0 and h['bytes']==c['size'] and h['sha256']==c['sha256']
   j=[json.loads(l) for l in e['commands']['journal']['stdout'].splitlines()];journals+=len(j)
   assert all(x['_BOOT_ID']==r['boot_id'].replace('-','') for x in j)
   bad=[x for x in j if re.search(r'\bERROR\b|\bCRITICAL\b|Traceback|\[error\]|\[crit\]|segfault|EXT4-fs error|I/O error|Buffer I/O|Kernel panic|Oops:|checksum error|DID_TIME_OUT|reset high-speed USB',str(x.get('MESSAGE','')))]
   assert not bad
  host_journal=[json.loads(l) for l in read('after-ro-check/host-journal.json')['stdout'].splitlines()]
  host_boot=[j for j in host_journal if int(j['__REALTIME_TIMESTAMP'])>=request['wall_ns']//1000]
  assert sum('New USB device found, idVendor=1d6b, idProduct=0106' in str(j.get('MESSAGE','')) for j in host_boot)==1
  assert not any(re.search(r'error|failed|timeout|reset high-speed|I/O|Oops',str(j.get('MESSAGE','')),re.I) for j in host_boot)
  assert any('Write Protect is on' in str(j.get('MESSAGE','')) for j in host_boot)
  ro=read('host-ro-check/result.json');assert ro['result']=='HOST_RO_MEDIA_PASS'
  assert ro['before']==ro['after']==dict(bytes=c['size'],sha256=c['sha256'])
  assert ro['scsi_write']['returncode']==7 and 'Data Protect' in ro['scsi_write']['stderr'] and 'Write protected' in ro['scsi_write']['stderr']
  assert ro['identity']['ro']=='1' and ro['boot_id']==first['boot_id']
  return dict(result='P3_S0_CLEAN_BOOT_INVARIANT_PASS',finding='fresh production boot restores attached RO MSD invariant',archive_sha256=digest,members=len(idx),boot_id=first['boot_id'],hashes_matched=10690,scsi_write_rejected=True,journal_records_reviewed=journals,host_boot_journal_records=len(host_boot),preparation_reboots=1,qualification_credit=0,accepted_cycles=0,historical_empty_lun_cause='UNASSIGNED',h3_root_cause='UNASSIGNED',h5='FAILED',h5r1='FAILED',p2='PASSED',p3='UNACCEPTED')
if __name__=='__main__':print(json.dumps(verify(),indent=2))
