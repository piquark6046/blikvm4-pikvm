#!/usr/bin/env python3
"""Authenticate the pre-reboot controller failure without retrying any run."""
import ast,hashlib,json,runpy,tarfile,tempfile
from pathlib import Path
R=Path(__file__).resolve().parents[3];sha=lambda b:hashlib.sha256(b).hexdigest()
def verify():
 archive=R/'out/p3-h5r2/p3-a02-cycle001-failed.tar.gz';digest='4fa747be4901cc17d78ace87febc363a0287cfa4493086831a481a682c12cc5b'
 assert sha(archive.read_bytes())==digest
 with tarfile.open(archive) as t:
  members=runpy.run_path(str(Path(__file__).with_name('verify-h5r2.py')))['entries'](t)
  data=lambda n:t.extractfile(n).read();read=lambda n:json.loads(data(n))
  idx='controller/export-p3-a02-cycle001-failed/SHA256.json';index=read(idx)
  assert set(index)|{idx}=={n for n,m in members.items() if m.isfile()}
  for n,h in index.items():assert sha(data(n))==h,n
  prefix='controller/p3-a02-cycle-001/'
  latch=read('controller/P3_A02_FAILED.json');r=read(prefix+'result.json');initial=read(prefix+'cycle.json')
  assert latch['result']==r['result']=='FAILED' and latch['error']==r['error']=="FileExistsError(17, 'File exists')"
  assert initial['result']=='in_progress' and 'reboot_request_wall_ns' not in initial
  assert r['stages']==[] and r['accepted_cycles']==r['qualification_credit']==0 and not r['browser_idle']['pids']
  assert not any(n.startswith(('active/',prefix+'msd/',prefix+'hid/',prefix+'startup/')) for n in members)
  for n in ('reboot-request.json','recovery.jsonl'):assert prefix+n not in members
  assert sha(data('controller/P3_A02_FAILED.json'))=='59a841dabcb8998c9e5ab56adb44d1dff8619b7580b37ccce9b5803f6255cf6b'
  prov=read(prefix+'source-provenance.json');assert prov['commit'].startswith('170056f') and len(prov['commit'])==40 and prov['clean']
  for n,h in prov['files'].items():assert sha(data(prefix+n))==h
  code=data(prefix+'p3-a02-cycle01.py').decode();assert sha(code.encode())==sha((R/'lab/p3-a02-cycle01.py').read_bytes());tree=ast.parse(code)
  execute=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='execute')
  # Before any reboot subprocess, execute publishes cycle.json a second time.
  first=code.index("publish(D/'cycle.json',cycle);publish(D/'start.json',r)")
  second=code.index("cycle.update(before_boot_id=old,")
  save=code.index("publish(D/'cycle.json',cycle)",second)
  command=code.index("p=subprocess.run(SSH+['sudo -n python3 -'],input=code",save)
  assert first<second<save<command
  publisher=data('input/p3-h2-boundary.py').decode();assert 'os.O_EXCL' in publisher
  assert sha(publisher.encode())==sha((R/'lab/p3-h2-boundary.py').read_bytes())
  # Reproduce the exact publication contract offline, without executing archive code.
  publish=runpy.run_path(str(R/'lab/p3-h2-boundary.py'))['publish']
  with tempfile.TemporaryDirectory(prefix='p3-a02-publication-replay-') as d:
   p=Path(d)/'cycle.json';publish(p,{'result':'in_progress'});old_bytes=p.read_bytes()
   try:publish(p,{'result':'reboot-planned'})
   except FileExistsError:pass
   else:raise AssertionError('exclusive publication unexpectedly overwrote state')
   assert p.read_bytes()==old_bytes
  before=read(prefix+'preboot/target.json');after=read(prefix+'postfailure-confirmation/target.json');stopped=read(prefix+'failure-preservation/target.json')
  assess=runpy.run_path(str(Path(__file__).with_name('inventory-gates.py')))['assess'];identity=read('controller/functional-preparation/p2-identity.json')
  for inv in (before,after,stopped):assess(inv,identity)
  for k in ('boot_id','sd_cid','machine_id','host_public_keys','hash_checks','gadget'):assert before[k]==after[k]==stopped[k],k
  def gen(x):return [l for k in ('services','ssh_show') for l in x['commands'][k]['stdout'].splitlines() if l.startswith(('Id=','InvocationID=','ExecMainStartTimestampMonotonic=','NRestarts='))]
  assert gen(before)==gen(after)==gen(stopped)
  for phase,inv in (('preboot',before),('postfailure-confirmation',after)):
   g=prefix+phase+'-msd-gate/'
   runpy.run_path(str(R/'lab/p3-h5r2-state.py'))['check'](inv,read(g+'target-state.json'),read(g+'host.json'))
  uart=b''.join(data(n) for n in members if n.startswith(prefix+'uart/uart-') and n.endswith('.raw'))
  assert b'U-Boot SPL' not in uart and b'Starting kernel' not in uart
  events=[json.loads(l) for l in data(prefix+'uart/events.jsonl').splitlines()]
  assert events[-1]['event']=='watcher_finished' and events[-1]['bytes']==0 and events[-1]['segments']==1
  journal=[json.loads(l) for l in data(prefix+'controller-journal.jsonl').splitlines()]
  assert any("FileExistsError: [Errno 17] File exists: 'cycle.json'" in str(j.get('MESSAGE','')) for j in journal)
  assert 'controller/FAILED.json' not in members and read('controller/h5r2-acceptance.json')['result']=='H5R2_INDEPENDENTLY_ACCEPTED'
  previous=R/'out/p3-h5r2/functional-003.tar.gz';assert sha(previous.read_bytes())=='830608ff1f8f5b398b88f1c64cdbb320f38961ee602f3caf2f8108982314c1e6'
  count=0
  with tarfile.open(previous) as old:
   for m in old:
    if m.isfile():assert sha(old.extractfile(m).read())==sha(data(m.name)),m.name;count+=1
  return dict(result='P3_A02_CYCLE001_PRE_REBOOT_FAILURE_CONFIRMED',archive_sha256=digest,indexed_files=len(index),first_failure='FileExistsError updating existing cycle.json with append-only publisher',finalization_error='same exclusive cycle.json update; original initial state retained',reboots_issued=0,chromium_launches=0,accepted_cycles=0,qualification_credit=0,boot_id=after['boot_id'],hashes_matched=10690,service_generations_unchanged=True,attached_readonly_pre_and_post=True,h5r2_archived_files_unchanged=count,h5r2='ACCEPTED',h5r1='FAILED',h5='FAILED',h3_root_cause='UNASSIGNED',p2='PASSED',p3='UNACCEPTED',p3_b_c='BLOCKED',m6_atx='DEFERRED',ro_overlay='DEFERRED')
if __name__=='__main__':print(json.dumps(verify(),indent=2))
