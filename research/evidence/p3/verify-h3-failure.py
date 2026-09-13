#!/usr/bin/env python3
"""Replay H3's failed first Chromium launch; cannot award qualification credit."""
import argparse
import hashlib
import io
import json
from pathlib import Path,PurePosixPath
import re
import runpy
import tarfile

if not __debug__:raise SystemExit('assertions required')
p=argparse.ArgumentParser();p.add_argument('archive',type=Path);p.add_argument('--sha256',required=True)
p.add_argument('--permission-archive',type=Path,default=Path('out/p3-h3/permission-only.tar.gz'))
a=p.parse_args()
def sha(b):return hashlib.sha256(b).hexdigest()
assert sha(a.archive.read_bytes())==a.sha256
assert sha(a.permission_archive.read_bytes())=='2158a52d913639d4547f950e54d6d7a2c0132d0fcb5bea539319c5ecfa2c71b0'
assess=runpy.run_path(str(Path(__file__).with_name('inventory-gates.py')))['assess']
with tarfile.open(a.archive) as t:
    members={}
    for m in t:
        n=PurePosixPath(m.name)
        assert not n.is_absolute() and '..' not in n.parts and m.name not in members
        assert m.isfile() or m.isdir()
        members[m.name]=m
    def data(n):return t.extractfile(n).read()
    def read(n):return json.loads(data(n))
    index_name='controller/snapshot-h3-failed/SHA256.json';index=read(index_name)
    assert set(index)|{index_name}=={n for n,m in members.items() if m.isfile()}
    for n,h in index.items():assert sha(data(n))==h,n
    # All bytes in the independently replayed permission snapshot remain frozen.
    with tarfile.open(a.permission_archive) as old:
        for m in old:
            if m.isfile():assert sha(old.extractfile(m).read())==sha(data(m.name)),m.name
    prefix='controller/chromium-preflight-001/';name='chromium-preflight-001'
    r=read(prefix+'result.json');review=read(prefix+'failure-review/result.json')
    assert r['result']=='FAILED' and r['error']=="RuntimeError('missing launch gate')" and not r['stages']
    assert read('controller/FAILED.json')['error']==r['error']
    assert r['qualification_credit']==r['accepted_cycles']==r['reboots']==0
    assert not any('/chromium-preflight-002' in n or '/chromium-preflight-003' in n for n in members)
    assert not any(n.startswith(prefix+'hid/') for n in members)
    browser=read('sealed/'+name+'/msd/browser-result.json');functional=read(prefix+'msd/result.json')
    assert browser['result']==functional['result']=='failed'
    assert not browser['steps'] and not functional['stages'] and not functional['transitions']
    assert 'signal=SIGTRAP' in browser['error'] and '<launched> pid=' in browser['error']
    assert browser==functional['browser']
    gate=read('sealed/'+name+'/msd/launch-audit-001.json')
    assert gate==read(prefix+'msd/launch-audit-001.json')
    assert not any(n.endswith('/launch-audit-002.json') for n in members)
    operations=0
    def effective(e,active):
        global operations
        assert (e['uid'],e['gid'],e['groups'])==(995,983,[983])
        assert e['writable_leaves']==([active] if active else [])
        assert e['operations'] and all(o['passed'] for o in e['operations'])
        operations+=len(e['operations'])
    base='/var/lib/blikvm-p3-h3';active=base+'/active/'+name;legacy='/var/lib/blikvm-p3-legacy'
    effective(gate,active)
    for n in ('before-target-audit.json','msd-before-audit.json','failure-review/after-seal-audit.json'):
        audit=read(prefix+n);assert audit['returncode']==0
        effective(audit['effective'],None if n.startswith('failure-review') else active)
        assert audit['requirements']['roots'][:2]==[base,legacy]
        assert legacy in audit['requirements']['barriers'] and base+'/sealed' in audit['requirements']['barriers']
        assert all(not {'system.posix_acl_access','system.posix_acl_default'}&v['xattrs'].keys() for v in audit['ancestors'].values())
    post=read(prefix+'failure-review/after-seal-audit.json')['effective']['operations']
    for n in ('perm-001','perm-002','perm-003',name):
        root=base+'/sealed/'+n
        assert any(o['path']==root and o['operation']=='traverse' and o['errno']==13 for o in post)
        file=root+('/msd/browser-result.json' if n==name else '/unknown-0777/fixture')
        for op in ('open_write','truncate','rename','unlink'):
            assert any(o['path']==file and o['operation']==op and o['errno']==13 for o in post)
    protected=read(prefix+'protected-before.json')
    assert protected==read(prefix+'failure-review/protected-after.json')
    probe=legacy+'/p3-context/a01-smoke/browser-msd/.h2-probe-1cd9f4afd2db4fa3aeed136f35858e42'
    assert protected[probe]['size']==0 and protected[probe]['sha256']==sha(b'') and protected[probe]['uid']==995
    assert protected[str(PurePosixPath(probe).parent)]['mode']==0o777
    seal=r['failure_seal'];assert seal==read('controller/'+name+'-seal.json')
    assert not seal['browser_exit']['pids'] and seal['method']=='atomic_rename_under_root_0700'
    original=read('controller/'+name+'-metadata.json')['paths']
    assert sha(data('controller/'+name+'.tar.gz'))==seal['sha256']
    with tarfile.open(fileobj=io.BytesIO(data('controller/'+name+'.tar.gz'))) as inner:
        im=inner.getmembers();assert len(im)==len(original)==25
        for m in im:
            path=base+'/active/'+m.name;old=original[path];new=members['sealed/'+m.name]
            assert (m.uid,m.gid,m.mode)==(new.uid,new.gid,new.mode)==(old['uid'],old['gid'],old['mode'])
            if m.isfile():assert sha(inner.extractfile(m).read())==sha(data('sealed/'+m.name))==old['sha256']
    before=read(prefix+'before/target.json');after=read(prefix+'failure-preservation/target.json')
    identity=read('controller/preparation/p2-identity.json')
    for inv in (before,after):assess(inv,identity)
    for k in ('hash_checks','boot_id','machine_id','host_public_keys','sd_cid'):assert before[k]==after[k]
    assert len(before['hash_checks'])==10690
    def gen(inv):return [l for key in ('services','ssh_show') for l in inv['commands'][key]['stdout'].splitlines()
                       if l.startswith(('Id=','InvocationID=','ExecMainStartTimestampMonotonic=','NRestarts='))]
    assert gen(before)==gen(after)
    def errors(inv):
        return [(j['__MONOTONIC_TIMESTAMP'],j.get('_SYSTEMD_UNIT'),j.get('MESSAGE'))
                for j in map(json.loads,inv['commands']['journal_json']['stdout'].splitlines())
                if re.search(r'\berror\b|\bcritical\b|\bfailed\b|Traceback|segfault|Kernel panic|Oops',str(j.get('MESSAGE','')),re.I)]
    assert errors(before)==errors(after) and len(errors(after))==9
    with tarfile.open(fileobj=io.BytesIO(data('controller/legacy-00.tar.gz'))) as legacy_archive:
        frozen_h2=legacy_archive.extractfile('blikvm-p3/h2-failed-evidence.tar.gz').read()
    assert sha(frozen_h2)=='1bb8f7076d86de563381e2736169698589c03f728f5d09c6fac148943b42b332'
    with tarfile.open(fileobj=io.BytesIO(frozen_h2)) as h2_archive:
        h2_target=json.load(h2_archive.extractfile('attempt/preflight-001/controller/failure-preservation/target.json'))
    assert errors(after)==errors(h2_target) and gen(after)==gen(h2_target)
    assert not read(prefix+'failure-review/browser-processes.json')['pids']
    assert review['active_leaves']==0 and review['protected_inputs_unchanged'] and not review['retry_performed']
    for source in Path(__file__).resolve().parents[3].joinpath('lab').glob('p3-h3-*'):
        if source.is_file():assert sha(source.read_bytes())==sha(data('controller/snapshot-h3-failed/'+source.name)) if source.suffix=='.py' else sha(source.read_bytes())==sha(data('controller/snapshot-h3-failed/context/'+source.name))
    result={'result':'H3_FAILED_CONFIRMED','scope':'BRIDGE_HARNESS_ONLY','archive_sha256':a.sha256,
      'indexed_files':len(index),'permission_transitions_passed':3,'chromium_launches_attempted':1,
      'chromium_smokes_completed':0,'failed_at':'first Chromium launch exited SIGTRAP before first browser UI stage',
      'controller_error':r['error'],'crash_root_cause':'unassigned','permission_syscall_operations':operations,
      'post_seal_audit_passed':True,'sealed_browser_files_immutable_to_uid995':True,
      'legacy_probe_preserved':True,'protected_inputs_unchanged':True,
      'target_hashes_matched':10690,'boot_id':before['boot_id'],'service_generations_unchanged':True,
      'target_journal_records_reviewed':len(after['commands']['journal_json']['stdout'].splitlines()),
      'historical_target_error_messages_unchanged':9,'new_target_error_messages':0,
      'browser_processes_remaining':0,'reboots':0,'accepted_cycles':0,'qualification_credit':0,
      'p2':'PASSED','p3':'UNACCEPTED','p3_b_p3_c':'UNSTARTED'}
print(json.dumps(result,indent=2))
