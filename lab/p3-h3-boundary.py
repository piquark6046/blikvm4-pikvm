#!/usr/bin/env python3
"""Bridge-only ancestor isolation, whole-namespace syscall audit and rename seal.

No target operations. A failed audit is never repaired into a pass. Trusted
publication and untrusted JSON reads use no-follow directory-relative opens.
"""
import errno
import hashlib
import json
import os
from pathlib import Path
import pwd
import runpy
import stat
import subprocess
import sys
import tarfile
import time
import uuid

B = runpy.run_path(str(Path(__file__).with_name('p3-h2-boundary.py')))
require, publish, read_json = B['require'], B['publish'], B['read_json']
metadata, no_acl, trusted_dir = B['metadata'], B['no_acl'], B['trusted_dir']
browser_idle = B['browser_idle']
BASE = Path('/var/lib/blikvm-p3-h3')
LEGACY = Path('/var/lib/blikvm-p3-legacy')


def digest(path):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, 'rb') as f:
        require(stat.S_ISREG(os.fstat(f.fileno()).st_mode), 'not regular')
        return hashlib.file_digest(f, 'sha256').hexdigest()


def manifest(root, legacy=False):
    """Complete lstat inventory; legacy links are recorded, never traversed."""
    root = Path(root)
    result = {}
    def visit(p):
        m = no_acl(p)
        require(m['type'] in (stat.S_IFDIR, stat.S_IFREG, stat.S_IFLNK), 'special entry: '+str(p))
        if not legacy:
            require(m['type'] != stat.S_IFLNK, 'symlink output: '+str(p))
        if m['type'] == stat.S_IFREG:
            require(legacy or m['nlink'] == 1, 'hardlinked output: '+str(p))
            m['sha256'] = digest(p)
            fd = os.open(p, os.O_RDONLY | os.O_NOFOLLOW)
            os.fsync(fd); os.close(fd)
        result[str(p)] = m
        if m['type'] == stat.S_IFDIR:
            for name in sorted(os.listdir(p)):
                visit(p/name)
            fd = trusted_dir(p); os.fsync(fd); os.close(fd)
    visit(root)
    return result


def archive(root, dest, record, legacy=False):
    browser_idle()
    before = manifest(root, legacy)
    publish(record, {'root': str(root), 'paths': before, 'phase': 'before_archive_and_rename'})
    fd = os.open(dest, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o400)
    with os.fdopen(fd, 'wb') as f:
        with tarfile.open(fileobj=f, mode='w:gz', dereference=False) as t:
            t.add(root, arcname=Path(root).name)
        f.flush(); os.fsync(f.fileno())
    with tarfile.open(dest) as t:
        seen = set()
        for entry in t:
            p = str(Path(root).parent/entry.name)
            require(p in before and p not in seen, 'unexpected/duplicate archive member')
            seen.add(p); m = before[p]
            require((entry.uid,entry.gid,entry.mode) == (m['uid'],m['gid'],m['mode']), 'archive metadata mismatch')
            if entry.isfile():
                require(hashlib.sha256(t.extractfile(entry).read()).hexdigest() == m['sha256'], 'archive content mismatch')
            elif entry.issym():
                require(legacy and entry.linkname == m['link'], 'archive link mismatch')
            else:
                require(entry.isdir(), 'unexpected archive type')
        require(seen == set(before), 'archive incomplete')
    require(manifest(root, legacy) == before, 'tree changed while archiving')
    fd = trusted_dir(Path(dest).parent); os.fsync(fd); os.close(fd)
    return {'archive': str(dest), 'sha256': digest(dest), 'manifest': str(record), 'members': len(before)}


def seal(leaf, base=BASE):
    leaf, base = Path(leaf), Path(base)
    require(leaf.parent == base/'active' and leaf.name not in ('', '.', '..'), 'invalid active leaf')
    require(no_acl(base/'sealed')['uid'] == 0 and no_acl(base/'sealed')['mode'] == 0o700, 'sealed boundary drift')
    require(not (base/'sealed'/leaf.name).exists(), 'sealed nonce reused')
    browser_idle()
    r = archive(leaf, base/'controller'/(leaf.name+'.tar.gz'), base/'controller'/(leaf.name+'-metadata.json'))
    browser_idle()
    source = trusted_dir(base/'active'); dest = trusted_dir(base/'sealed')
    try:
        os.rename(leaf.name, leaf.name, src_dir_fd=source, dst_dir_fd=dest)
        os.fsync(source); os.fsync(dest)
    finally:
        os.close(source); os.close(dest)
    r.update(source=str(leaf), sealed=str(base/'sealed'/leaf.name), method='atomic_rename_under_root_0700', browser_exit=browser_idle())
    publish(base/'controller'/(leaf.name+'-seal.json'), r)
    return r


def worker(payload):
    result = {'uid': os.getuid(), 'gid': os.getgid(), 'groups': os.getgroups(),
              'operations': [], 'visited': [], 'blocked': [], 'writable_leaves': []}
    def op(p, name, fn, allow=False):
        r = {'path': str(p), 'operation': name, 'expected': 'allow' if allow else 'deny'}
        try:
            fn(); r.update(errno=0, outcome='allowed')
        except OSError as e:
            r.update(errno=e.errno, outcome='denied')
        r['passed'] = r['errno'] == 0 if allow else r['errno'] in (errno.EACCES, errno.EPERM, errno.EROFS)
        result['operations'].append(r)
        if not r['passed']:
            print(json.dumps(result), flush=True); raise SystemExit(1)
    def opening(p, flags):
        fd = os.open(p, flags | os.O_NOFOLLOW, 0o600); os.close(fd)
    def write_sync(p):
        fd = os.open(p, os.O_WRONLY | os.O_NOFOLLOW)
        os.write(fd,b'disposable H3 permission fixture'); os.fsync(fd); os.close(fd)
    token = '.h3-probe-'+uuid.uuid4().hex
    active = Path(payload['active']) if payload['active'] else None
    # Explicit barriers are tested before the global traversal. Descendant modes
    # are immaterial: even a known full path must fail at its ancestor.
    for p in map(Path, payload['barriers']):
        op(p,'traverse',lambda p=p: os.chdir(p))
        op(p/token,'create',lambda p=p: opening(p/token,os.O_WRONLY|os.O_CREAT|os.O_EXCL))
    for p in map(Path, payload['reads']):
        op(p,'required_read',lambda p=p: opening(p,os.O_RDONLY),True)
    for p in map(Path, payload['traverse']):
        op(p,'required_traverse',lambda p=p: os.chdir(p),True)
    os.chdir('/')
    if active:
        op(active,'current_traverse',lambda: os.chdir(active),True)
        f,g = active/token,active/(token+'-renamed')
        op(f,'create',lambda: opening(f,os.O_CREAT|os.O_EXCL|os.O_WRONLY),True)
        op(f,'write_fsync',lambda: write_sync(f),True)
        op(f,'rename',lambda: os.rename(f,g),True)
        op(g,'unlink',lambda: os.unlink(g),True)
        fd=os.open(active,os.O_DIRECTORY);os.fsync(fd);os.close(fd)
        os.chdir('/'); result['writable_leaves'].append(str(active))
    def protected(p, is_dir):
        if is_dir:
            op(p/token,'create',lambda: opening(p/token,os.O_CREAT|os.O_EXCL|os.O_WRONLY))
            op(p/token,'mkdir',lambda: os.mkdir(p/token))
        else:
            # Stop on write-open success before attempting truncation of evidence.
            op(p,'open_write',lambda: opening(p,os.O_WRONLY))
            op(p,'truncate',lambda: opening(p,os.O_WRONLY|os.O_TRUNC))
            op(p,'rename',lambda: os.rename(p,p.with_name(p.name+token)))
            op(p,'unlink',lambda: os.unlink(p))
    seen=set()
    def walk(p):
        if str(p) in seen:return
        seen.add(str(p));result['visited'].append(str(p))
        if active and (p == active or active in p.parents):return
        try:m=p.lstat()
        except PermissionError:
            result['blocked'].append(str(p));protected(p,False);return
        require(not stat.S_ISLNK(m.st_mode), 'unexpected namespace symlink: '+str(p))
        if stat.S_ISDIR(m.st_mode):
            protected(p,True)
            try:names=os.listdir(p)
            except PermissionError:result['blocked'].append(str(p));return
            for n in sorted(names):walk(p/n)
        elif stat.S_ISREG(m.st_mode):protected(p,False)
        else:raise RuntimeError('special namespace entry: '+str(p))
    for p in map(Path,payload['roots']):walk(p)
    # Mutation operations on root-only canaries work even without directory traversal.
    for p in map(Path,payload['protected_files']):protected(p,False)
    for p in map(Path,payload['protected_dirs']):protected(p,True)
    print(json.dumps(result),flush=True)


def audit(active, output, config, base=BASE):
    browser_idle(); base=Path(base)
    active = Path(active) if active else None
    actual = list((base/'active').iterdir())
    require(actual == ([active] if active else []), 'extra active leaf')
    roots = [base, Path(config['legacy'])] + [Path(p) for p in config['protected_roots']]
    ancestors={}; inventories={}
    # Complete root inventory supplies ACL/stat provenance; the worker independently
    # walks all reachable members as uid 995, without a list of historical leaves.
    for root in roots:
        canonical=root.resolve(strict=True)
        require(root == canonical, 'noncanonical audit root: '+str(root))
        inventories[str(root)] = manifest(root, legacy=(root != base))
        for q in [root,*root.parents]:ancestors[str(q)]=no_acl(q)
    for q in base.rglob('*'):
        if active and (q == active or active in q.parents):continue
        require(not q.is_symlink(), 'symlink in trusted namespace')
    payload={'active':str(active) if active else None, 'roots':[str(p) for p in roots],
             'barriers':[config['legacy'],str(base/'sealed'),str(base/'controller')]+config.get('cross_run',[]),
             'reads':config['reads'], 'traverse':[str(base),str(base/'active')],
             'protected_dirs':list(ancestors),
             'protected_files':[str(base/'controller/canary'),str(base/'input/canary')]+config.get('protected_files',[])}
    q=subprocess.run(['runuser','-u','p3-browser','--',sys.executable,str(Path(__file__).resolve()),'--worker'],
                     input=json.dumps(payload),capture_output=True,text=True)
    try:effective=json.loads(q.stdout)
    except ValueError:effective={'stdout':q.stdout,'stderr':q.stderr}
    r={'requirements':payload,'ancestors':ancestors,'inventories':inventories,
       'realpaths':{str(p):str(p.resolve(strict=True)) for p in roots},
       'mountinfo':Path('/proc/self/mountinfo').read_text(),
       'effective':effective,'returncode':q.returncode,'checked_ns':time.time_ns()}
    publish(output,r)
    require(q.returncode == 0,'global permission auditor FAILED: '+str(output))
    require((effective['uid'],effective['gid'],effective['groups']) == (995,983,[983]),'browser identity drift')
    require(effective['writable_leaves'] == ([str(active)] if active else []),'writable evidence leaf mismatch')
    return r


if __name__ == '__main__':
    require(sys.argv[1:] == ['--worker'],'import controller functions')
    worker(json.load(sys.stdin))
