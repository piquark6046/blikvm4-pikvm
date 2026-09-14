#!/usr/bin/env python3
"""Independent offline archive authentication and current-state continuity."""
import hashlib,json,tarfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
sha=lambda b:hashlib.sha256(b).hexdigest()
def verify():
 inv=json.loads((Path(__file__).with_name('s0-boot-invariant.json')).read_text())
 archive=ROOT/'out/p3-s0/current-empty.tar.gz'
 assert sha(archive.read_bytes())==inv['current_snapshot_sha256']
 old=ROOT/'out/p3-h5r1/functional-001-failed.tar.gz'
 assert sha(old.read_bytes())=='4fac32a311fd4649a1f2ff13003a3afee4be66b3c193b49bfd626e38d4968c48'
 with tarfile.open(archive) as t,tarfile.open(old) as h:
  read=lambda n:json.load(t.extractfile('snapshot/'+n))
  idx=read('SHA256.json');names=[m.name for m in t if m.isfile()]
  assert len(names)==len(set(names)) and set(idx)=={n.removeprefix('snapshot/') for n in names}-{'SHA256.json'}
  for n,d in idx.items():assert sha(t.extractfile('snapshot/'+n).read())==d
  r=read('current-empty-complete/inventory/target.json');e=read('current-empty-complete/target-extra.json')
  previous=json.load(h.extractfile('controller/functional-001/failure-preservation/target.json'))
  for k in ('boot_id','machine_id','sd_cid','host_public_keys','hash_checks','gadget'):assert r[k]==previous[k],k
  def gen(x):return [l for k in ('services','ssh_show') for l in x['commands'][k]['stdout'].splitlines() if l.startswith(('Id=','InvocationID=','ExecMainStartTimestampMonotonic=','NRestarts='))]
  assert gen(r)==gen(previous)
  assert len(r['hash_checks'])==10690 and all(v['matches'] for v in r['hash_checks'].values())
  assert json.loads(r['commands']['root']['stdout'])['filesystems'][0]['source']=='/dev/mmcblk0p1'
  assert not r['commands']['failed_units']['stdout'].strip()
  assert e['boot_id']==r['boot_id'] and float(e['uptime'].split()[0])>65000
  lun='blikvm_m5/functions/mass_storage.g4/lun.0/'
  assert e['gadget'][lun+'file']['hex']==''
  for k in ('ro','cdrom','removable','nofua','inquiry_string'):assert bytes.fromhex(e['gadget'][lun+k]['hex']).decode().strip()==inv[k]
  assert e['gadget'][lun+'forced_eject']['errno']==13
  api=json.loads(e['commands']['api']['stdout'])['result'];assert api['drive']['connected'] is False
  assert api['drive']['image']['name']==inv['api_image'] and not api['drive']['rw']
  for p in ('/usr/share/g4-storage.img',inv['file']):assert e['files'][p]['sha256']==inv['sha256'] and e['files'][p]['size']==inv['size']
  assert e['files']['/usr/bin/gadget-storage']['sha256']==inv['gadget_setup_sha256']
  assert e['files']['/usr/lib/kvmd-msd/media-helper']['sha256']==inv['media_helper_sha256']
  host=read('current-empty-complete/host-storage-objects.json');assert len(host)==1 and host[0]['attrs']['ro']=='1\n'
  media=read('current-empty-complete/host-media-hash.json');assert media['returncode']!=0 and media['bytes']==0
  journal=[json.loads(l) for l in e['commands']['journal']['stdout'].splitlines()]
  assert all(j['_BOOT_ID']==r['boot_id'].replace('-','') for j in journal)
  return dict(result='S0_CURRENT_EMPTY_VERIFIED',archive_sha256=inv['current_snapshot_sha256'],members=len(idx),boot_id=r['boot_id'],hashes_matched=10690,service_generations_unchanged=True,api_connected=False,host_objects_present=True,host_media_readable=False,journal_records=len(journal),journal_first_monotonic_us=min(int(j['__MONOTONIC_TIMESTAMP']) for j in journal),qualification_credit=0)
if __name__=='__main__':print(json.dumps(verify(),indent=2))
