#!/usr/bin/env python3
"""Independent H3 permission replay; no extraction or deployed code execution."""
import argparse
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import stat
import tarfile

p=argparse.ArgumentParser();p.add_argument('archive',type=Path);p.add_argument('--sha256',required=True);a=p.parse_args()
if not __debug__:raise SystemExit('assertions required')
def sha(b):return hashlib.sha256(b).hexdigest()
assert sha(a.archive.read_bytes())==a.sha256

def entries(t):
    result={}
    for m in t:
        q=PurePosixPath(m.name)
        assert not q.is_absolute() and '..' not in q.parts and m.name not in result
        assert m.isdir() or m.isfile() or m.issym()
        result[m.name]=m
    return result

with tarfile.open(a.archive) as t:
    outer=entries(t)
    def data(n):return t.extractfile(n).read()
    def read(n):return json.loads(data(n))
    index_name='controller/snapshot-permission-only/SHA256.json'
    index=read(index_name)
    assert set(index)|{index_name}=={n for n,m in outer.items() if m.isfile()}
    for n,h in index.items():assert sha(data(n))==h,n
    result=read('controller/permission-result.json')
    assert result['result']=='PERMISSION_ONLY_PASS_PENDING_INDEPENDENT_REPLAY'
    assert result['qualification_credit']==result['reboots']==result['accepted_cycles']==0
    assert not result['target_contacted'] and not result['chromium_launched']
    assert len(result['transitions'])==3 and 'controller/FAILED.json' not in outer
    quarantine=read('controller/quarantine.json');legacy=quarantine['legacy']
    assert (quarantine['metadata']['uid'],quarantine['metadata']['gid'],quarantine['metadata']['mode'])==(0,0,0o700)
    assert not quarantine['descendant_chmod_chown']
    base='/var/lib/blikvm-p3-h3'
    def check_archive(archive_name,metadata_name,original_root,allow_links=False):
        expected=read(metadata_name)['paths']
        with tarfile.open(fileobj=io.BytesIO(data(archive_name))) as inner:
            im=entries(inner);assert len(im)==len(expected)
            for n,m in im.items():
                path=str(PurePosixPath(original_root).parent/n);old=expected[path]
                assert (m.uid,m.gid,m.mode)==(old['uid'],old['gid'],old['mode'])
                assert not {'system.posix_acl_access','system.posix_acl_default'}&old['xattrs'].keys()
                if m.isfile():assert sha(inner.extractfile(m).read())==old['sha256']
                elif m.issym():assert allow_links and old['link']==m.linkname
                else:assert m.isdir()
        return expected
    freeze=read('controller/legacy-freeze.json');assert len(freeze['records'])==4
    for i,root in enumerate(freeze['roots']):
        record=freeze['records'][i]
        assert sha(data('controller/'+PurePosixPath(record['archive']).name))==record['sha256']
        m=check_archive(f'controller/legacy-{i:02d}.tar.gz',f'controller/legacy-{i:02d}-metadata.json',root,True)
        if root.endswith('/p3-context'):
            old=root+'/a01-smoke/browser-msd';assert m[old]['mode']==0o777
            probe=old+'/.h2-probe-1cd9f4afd2db4fa3aeed136f35858e42'
            assert (m[probe]['size'],m[probe]['uid'],m[probe]['gid'])==(0,995,983)
            assert m[probe]['sha256']==sha(b'')
        if root=='/home/user/blikvm-p3':
            for name,h in read('controller/existing-archives.json').items():assert m[root+'/'+name]['sha256']==h
    operations=0
    for i in range(1,4):
        name=f'perm-{i:03d}';root=base+'/active/'+name
        seal=read(f'controller/{name}-seal.json')
        assert seal['method']=='atomic_rename_under_root_0700' and not seal['browser_exit']['pids']
        assert seal['source']==root and seal['sealed']==base+'/sealed/'+name
        assert sha(data('controller/'+name+'.tar.gz'))==seal['sha256']
        m=check_archive('controller/'+name+'.tar.gz','controller/'+name+'-metadata.json',root)
        assert m[root+'/unknown-0777']['mode']==0o777
        for path,old in m.items():
            n='sealed/'+name+path.removeprefix(root);new=outer[n]
            assert (new.mode,new.uid,new.gid)==(old['mode'],old['uid'],old['gid'])
            if new.isfile():assert sha(data(n))==old['sha256']
        for phase in ('before','after'):
            audit=read(f'controller/{name}-{phase}-audit.json');e=audit['effective'];req=audit['requirements']
            assert audit['returncode']==0 and (e['uid'],e['gid'],e['groups'])==(995,983,[983])
            assert e['writable_leaves']==([root] if phase=='before' else [])
            assert all(o['passed'] for o in e['operations']);operations+=len(e['operations'])
            assert base in req['roots'] and legacy in req['roots']
            assert legacy in req['barriers'] and base+'/sealed' in req['barriers']
            assert legacy+'/p3-context/a01-smoke/browser-msd' in req['barriers']
            for boundary in req['barriers']:
                assert any(o['path']==boundary and o['operation']=='traverse' and o['errno'] in (1,13) for o in e['operations'])
            for k,v in audit['ancestors'].items():
                assert not {'system.posix_acl_access','system.posix_acl_default'}&v['xattrs'].keys()
            assert audit['mountinfo'] and audit['realpaths'][legacy]==legacy
            for j in range(1,i+(phase=='after')):
                prior=f'{base}/sealed/perm-{j:03d}/unknown-0777'
                assert prior in req['barriers']
    print(json.dumps({'result':'H3_PERMISSION_ONLY_PASS','archive_sha256':a.sha256,'indexed_files':len(index),
       'legacy_archives_verified':4,'legacy_probe_preserved':True,'descendant_mode_0777_preserved':True,
       'permission_transitions':3,'audits':6,'syscall_operations':operations,
       'qualification_credit':0,'accepted_cycles':0,'target_contacted':False,'chromium_launched':False},indent=2))
