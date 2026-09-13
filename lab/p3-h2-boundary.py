#!/usr/bin/env python3
"""Bridge-only P3-H2 lifecycle and syscall auditor. No target operations.

The controller owns the namespace and every control file. Browser output is
untrusted even after exit. Archives preserve pre-seal ownership/modes; sealing
changes only the working copy. An unexpected operation is a hard failure.
"""
import errno
import hashlib
import json
import os
from pathlib import Path
import pwd
import stat
import subprocess
import sys
import tarfile
import time
import uuid

USER = 'p3-browser'
ACL_NAMES = ('system.posix_acl_access', 'system.posix_acl_default')


def require(value, message):
    if not value:
        raise RuntimeError(message)


def metadata(path):
    p = Path(path)
    s = p.lstat()
    attrs = {n: os.getxattr(p, n, follow_symlinks=False).hex()
             for n in os.listxattr(p, follow_symlinks=False)}
    return dict(uid=s.st_uid, gid=s.st_gid, mode=stat.S_IMODE(s.st_mode),
                type=stat.S_IFMT(s.st_mode), size=s.st_size, dev=s.st_dev,
                ino=s.st_ino, nlink=s.st_nlink, mtime_ns=s.st_mtime_ns,
                ctime_ns=s.st_ctime_ns, xattrs=attrs,
                link=os.readlink(p) if stat.S_ISLNK(s.st_mode) else None)


def no_acl(path):
    m = metadata(path)
    require(not set(ACL_NAMES).intersection(m['xattrs']), 'unexpected ACL: '+str(path))
    return m


def trusted_dir(path):
    """Open each ancestor without following links, starting at the root FD."""
    path = Path(path)
    require(path.is_absolute() and '..' not in path.parts, 'absolute canonical path required')
    fd = os.open('/', os.O_RDONLY | os.O_DIRECTORY)
    try:
        for name in path.parts[1:]:
            new = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = new
        return fd
    except BaseException:
        os.close(fd)
        raise


def read_json(path):
    """Pin parent and file; reject browser symlinks, hardlinks and special files."""
    p = Path(path)
    parent = trusted_dir(p.parent)
    try:
        fd = os.open(p.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
        with os.fdopen(fd, 'rb') as f:
            s = os.fstat(f.fileno())
            require(stat.S_ISREG(s.st_mode) and s.st_nlink == 1, 'not a single regular file')
            return json.load(f)
    finally:
        os.close(parent)


def publish(path, value, mode=0o600):
    """Exclusive publication relative to a non-browser-writable directory FD."""
    p = Path(path)
    fd = trusted_dir(p.parent)
    try:
        s = os.fstat(fd)
        require(s.st_uid == os.geteuid() and not s.st_mode & 0o022,
                'controller destination not exclusive: '+str(p.parent))
        out = os.open(p.name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                      mode, dir_fd=fd)
        with os.fdopen(out, 'wb') as f:
            f.write((json.dumps(value, indent=2)+'\n').encode())
            f.flush()
            os.fchmod(f.fileno(), mode)
            os.fsync(f.fileno())
        os.fsync(fd)
    finally:
        os.close(fd)


def browser_idle():
    u = pwd.getpwnam(USER)
    procs = []
    for p in Path('/proc').glob('[0-9]*/status'):
        try:
            fields = dict(x.split(':', 1) for x in p.read_text().splitlines() if ':' in x)
            if u.pw_uid in [int(x) for x in fields['Uid'].split()]:
                procs.append(p.parent.name)
        except FileNotFoundError:
            continue
    require(not procs, 'browser UID processes remain: '+repr(procs))
    return dict(uid=u.pw_uid, pids=procs, checked_ns=time.time_ns())


def tree(path):
    """Never recurse into a symlink. Reject special files and shared inodes."""
    p = Path(path)
    paths = [p]
    for root, dirs, files in os.walk(p, followlinks=False):
        paths.extend(Path(root)/n for n in sorted(dirs+files))
    records = {}
    for q in paths:
        m = no_acl(q)
        require(m['type'] in (stat.S_IFDIR, stat.S_IFREG), 'unexpected entry: '+str(q))
        if m['type'] == stat.S_IFREG:
            require(m['nlink'] == 1, 'hardlinked output: '+str(q))
            fd = os.open(q, os.O_RDONLY | os.O_NOFOLLOW)
            with os.fdopen(fd, 'rb') as f:
                m['sha256'] = hashlib.file_digest(f, 'sha256').hexdigest()
                os.fsync(f.fileno())
        else:
            fd = trusted_dir(q)
            os.fsync(fd)
            os.close(fd)
        records[str(q)] = m
    return records


def archive_then_seal(leaf, archive, record):
    browser_idle()
    leaf, archive = Path(leaf), Path(archive)
    before = tree(leaf)
    # Both the original metadata and original bytes are durable BEFORE chown/chmod.
    publish(record, dict(phase='original_before_seal', paths=before))
    with tarfile.open(archive, 'x:gz', dereference=False) as t:
        t.add(leaf, arcname=leaf.name, recursive=True)
    with archive.open('rb') as f:
        os.fsync(f.fileno())
        digest = hashlib.file_digest(f, 'sha256').hexdigest()
    fd = trusted_dir(archive.parent)
    os.fsync(fd)
    os.close(fd)
    with tarfile.open(archive) as t:
        require(len(t.getmembers()) == len(before), 'archive member count mismatch')
        for member in t:
            p = leaf.parent/member.name
            m = before[str(p)]
            require((member.uid, member.gid, member.mode) ==
                    (m['uid'], m['gid'], m['mode']), 'archive metadata mismatch')
            if member.isfile():
                require(hashlib.sha256(t.extractfile(member).read()).hexdigest() == m['sha256'],
                        'archive hash mismatch')
    # No browser process may retain a writable FD during revocation.
    browser_idle()
    require(tree(leaf) == before, 'output changed during archiving')
    for p in sorted(before, key=lambda x: len(Path(x).parts), reverse=True):
        os.chown(p, 0, 0, follow_symlinks=False)
        os.chmod(p, 0o500 if before[p]['type'] == stat.S_IFDIR else 0o400,
                 follow_symlinks=False)
    after = tree(leaf)
    require(all(after[p].get('sha256') == m.get('sha256') for p, m in before.items()),
            'sealing changed bytes')
    return dict(archive=str(archive), sha256=digest, original=before, sealed=after,
                browser_exit=browser_idle())


def worker(payload):
    """All probes run after runuser establishes the real UID/GID/groups."""
    result = dict(uid=os.getuid(), gid=os.getgid(), groups=os.getgroups(), operations=[])
    def op(path, name, fn, allowed=False):
        entry = dict(path=str(path), operation=name, expected='allow' if allowed else 'deny')
        try:
            fn()
            entry.update(outcome='allowed', errno=0)
        except OSError as e:
            entry.update(outcome='denied', errno=e.errno)
        entry['passed'] = (entry['errno'] == 0 if allowed else entry['errno'] in (errno.EACCES, errno.EPERM))
        result['operations'].append(entry)
        if not entry['passed']:
            print(json.dumps(result), flush=True)
            raise SystemExit(1)
    def opening(p, flags):
        fd = os.open(p, flags | os.O_NOFOLLOW)
        os.close(fd)
    token = '.h2-probe-'+uuid.uuid4().hex
    for p in payload['reads']:
        op(p, 'required_read', lambda p=p: opening(p, os.O_RDONLY), True)
    for p in payload.get('traverse', []):
        op(p, 'required_traverse', lambda p=p: os.chdir(p), True)
    os.chdir('/')
    active = payload.get('active')
    if active:
        op(active, 'traverse', lambda: os.chdir(active), True)
        f, g = Path(active)/token, Path(active)/(token+'-renamed')
        op(f, 'create', lambda: opening(f, os.O_WRONLY | os.O_CREAT | os.O_EXCL), True)
        op(f, 'write', lambda: f.write_bytes(b'disposable'), True)
        op(f, 'rename', lambda: os.rename(f, g), True)
        op(g, 'unlink', lambda: os.unlink(g), True)
        op(f, 'mkdir', lambda: os.mkdir(f), True)
        op(f, 'rmdir', lambda: os.rmdir(f), True)
        os.chdir('/')
    for p, m in payload['protected'].items():
        p = Path(p)
        if m['type'] == stat.S_IFDIR:
            op(p/token, 'create', lambda p=p: opening(p/token, os.O_CREAT | os.O_EXCL | os.O_WRONLY))
            op(p/token, 'mkdir', lambda p=p: os.mkdir(p/token))
            if p != Path('/'):
                op(p, 'rename_directory', lambda p=p: os.rename(p, p.with_name(p.name+token)))
        elif m['type'] == stat.S_IFREG:
            # If a non-destructive write-open succeeds, stop before truncation/unlink.
            op(p, 'open_write', lambda p=p: opening(p, os.O_WRONLY))
            op(p, 'truncate', lambda p=p: opening(p, os.O_WRONLY | os.O_TRUNC))
            op(p, 'rename', lambda p=p: os.rename(p, p.with_name(p.name+token)))
            op(p, 'unlink', lambda p=p: os.unlink(p))
        else:
            raise RuntimeError('unresolved protected type')
        op(p, 'chmod', lambda p=p,m=m: os.chmod(p, m['mode']))
        op(p, 'chown', lambda p=p,m=m: os.chown(p, m['uid'], m['gid']))
    print(json.dumps(result))


def audit(active, roots, reads, output, traverse=()):
    u = pwd.getpwnam(USER)
    protected = {}
    ancestors = {}
    # roots are explicit file/dir inventories, including every historical leaf.
    for raw in roots:
        p = Path(raw)
        for q in [p, *p.parents]:
            ancestors[str(q)] = no_acl(q)
        resolved = p.resolve(strict=True)
        for q in [resolved, *resolved.parents]:
            ancestors[str(q)] = no_acl(q)
        protected[str(resolved)] = no_acl(resolved)
    for raw in list(reads) + ([active] if active else []):
        for p in [Path(raw), *Path(raw).parents]:
            ancestors[str(p)] = no_acl(p)
    payload = dict(active=str(active) if active else None, protected=protected,
                   reads=[str(Path(p).resolve(strict=True)) for p in reads],
                   traverse=[str(p) for p in traverse])
    q = subprocess.run(['runuser','-u',USER,'--',sys.executable,str(Path(__file__).resolve()),
                        '--worker'], input=json.dumps(payload), text=True, capture_output=True)
    try:
        effective = json.loads(q.stdout)
    except ValueError:
        effective = dict(error=q.stderr, stdout=q.stdout)
    result = dict(ancestors=ancestors, requirements=payload, effective=effective,
                  returncode=q.returncode)
    publish(output, result)
    require(q.returncode == 0, 'permission syscall audit failed: '+str(output))
    require((effective['uid'], effective['gid'], effective['groups']) ==
            (u.pw_uid, u.pw_gid, [u.pw_gid]), 'unexpected browser credentials')
    require(all(x['passed'] for x in effective['operations']), 'permission operation failed')
    return result


if __name__ == '__main__':
    require(sys.argv[1:] == ['--worker'], 'controller must import this bridge-only module')
    worker(json.load(sys.stdin))
