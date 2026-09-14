#!/usr/bin/env python3
"""Aggregate independently replayed H5R2 archives and predecessor immutability."""
import hashlib,json,tarfile
from pathlib import Path
R=Path(__file__).resolve().parents[3];D=R/'out/p3-h5r2'
sha=lambda b:hashlib.sha256(b).hexdigest()
def verify():
 s0=json.loads((R/'research/evidence/p3/s0-acceptance.json').read_text());assert s0['result']=='P3_S0_CLEAN_BOOT_INVARIANT_PASS'
 inherit=json.loads((D/'minimal-inheritance-replay.json').read_text());assert inherit['result']=='H5R2_RUNTIME_INHERITANCE_ACCEPTED'
 summaries=[]
 for n in range(1,4):
  name=f'functional-{n:03d}';r=json.loads((D/(name+'-vm-replay.json')).read_text())
  assert r['result']=='H5R2_FUNCTIONAL_ACCEPTED' and r['name']==name
  assert sha((D/(name+'.tar.gz')).read_bytes())==r['archive_sha256']
  assert r['target_hashes_matched']==10690 and r['hid_stages']==47 and r['storage_checks']==8
  assert r['launches']==r['prospective_contracts']==r['generated_argv_records']==3
  assert r['qualification_credit']==r['accepted_cycles']==0
  summaries.append(r)
 with tarfile.open(D/'functional-003.tar.gz') as final:
  names={m.name for m in final if m.isfile()}
  unchanged=0
  for name in ('minimal-001','functional-001','functional-002'):
   with tarfile.open(D/(name+'.tar.gz')) as old:
    for m in old:
     if m.isfile():
      assert m.name in names and sha(old.extractfile(m).read())==sha(final.extractfile(m.name).read()),m.name
      unchanged+=1
  boot=s0['boot_id']
  for n in range(1,4):
   for phase in ('before','after'):
    prefix=f'controller/functional-{n:03d}/{phase}'
    inv=json.load(final.extractfile(prefix+'/target.json'));gate=json.load(final.extractfile(prefix+'-msd-gate/result.json'))
    assert inv['boot_id']==gate['boot_id']==boot
    assert gate['file']=='/usr/share/kvmd-msd/images/g4-storage.img' and gate['connected'] and gate['ro']==1
  assert 'controller/FAILED.json' not in names
 return dict(result='H5R2_INDEPENDENTLY_ACCEPTED',s0_clean_boot_invariant='PASS',minimal_sanity='PASS',runtime_inheritance='PASS',functional_preflights=3,attached_preconditions=3,attached_postconditions=3,boot_id=boot,target_hashes_matched=10690,chromium_launches=9,hid_stages=141,msd_storage_checks=24,predecessor_files_unchanged=unchanged,archives=[dict(name=r['name'],sha256=r['archive_sha256']) for r in summaries],qualification_credit=0,accepted_cycles=0,h3_root_cause='UNASSIGNED',h5='FAILED',h5r1='FAILED because its target prerequisite was false before launch',h5r2='prospectively qualifies the browser harness from a proven boot state',p2='PASSED',p3='UNACCEPTED',p3_b_c='BLOCKED',m6_atx='DEFERRED',ro_overlay='DEFERRED')
if __name__=='__main__':print(json.dumps(verify(),indent=2))
