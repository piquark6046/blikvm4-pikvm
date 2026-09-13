#!/usr/bin/env python3
"""Bridge-only effective access inventory, run before each P3 Chromium launch."""
import hashlib
import json
import os
from pathlib import Path
import pwd
import subprocess
import sys

USER = 'p3-browser'
CONTEXT = Path('/var/lib/blikvm-p3-browser')

def inventory(output):
    output = Path(output).resolve()
    user = pwd.getpwnam(USER)
    os.chown(output, user.pw_uid, user.pw_gid)
    output.chmod(0o750)
    private = CONTEXT / 'private'
    reads = [private / n for n in ('ca.crt', 'credentials.json')]
    reads += [CONTEXT / 'lab' / n for n in ('msd-browser.mjs', 'hid-browser.mjs')]
    reads += [CONTEXT / 'out/kvmd-web/browser/node_modules/playwright/package.json']
    reads += [CONTEXT / 'out/kvmd-web/browser/browsers/chromium-1208/chrome-linux64/chrome',
              Path('/usr/bin/node'), Path('/usr/bin/xvfb-run')]
    protected = [Path('/home/user/blikvm-msd/private'), Path('/home/user/blikvm-p3'),
                 Path('/home/user/blikvm-p3/a01'), Path('/home/user/blikvm-p3/preparation'),
                 Path('/home/user/blikvm-msd/p3-context/a01-smoke'),
                 Path('/home/user/blikvm-p2'),
                 Path('/home/user/.local/share/blikvm-m7'), private]
    protected += list(private.iterdir())
    protected += list(Path('/home/user/blikvm-msd/private').iterdir())
    parents = set()
    for p in reads + [output]:
        parents.update(p.parents)
        parents.update(p.resolve().parents)
    paths = sorted(set(reads + protected + list(parents) + [output]))
    stats = {}
    for p in paths:
        s = p.stat()
        stats[str(p)] = dict(uid=s.st_uid, gid=s.st_gid, mode=oct(s.st_mode & 0o7777),
                             resolved=str(p.resolve()))
    payload = dict(paths=[str(p) for p in paths], reads=[str(p) for p in reads],
                   protected=[str(p) for p in protected], parents=[str(p) for p in parents],
                   output=str(output), negative=[str(private/'credentials.json'),
                       '/home/user/blikvm-msd/private/credentials.json'])
    code = '''import errno,json,os,sys
p=json.load(sys.stdin)
r={'uid':os.getuid(),'gid':os.getgid(),'groups':os.getgroups(),'access':{}}
for name in p['paths']:
 r['access'][name]={k:os.access(name,v,effective_ids=True) for k,v in [('r',os.R_OK),('w',os.W_OK),('x',os.X_OK)]}
r['negative_open_write']={}
for name in p['negative']:
 try:
  fd=os.open(name,os.O_WRONLY);os.close(fd);r['negative_open_write'][name]='UNEXPECTED_WRITE_ACCESS'
 except OSError as e:r['negative_open_write'][name]=e.errno
# Exercise create, atomic publication, read, and cleanup in a fresh output directory.
f=p['output']+'/.permission-probe.tmp';g=p['output']+'/.permission-probe'
with open(f,'x') as h:h.write('probe')
os.rename(f,g)
with open(g) as h:assert h.read()=='probe'
os.unlink(g)
r['create_rename_read_cleanup']=True
print(json.dumps(r))
'''
    q = subprocess.run(['runuser','-u',USER,'--','python3','-c',code],
                       input=json.dumps(payload), text=True, capture_output=True, check=True)
    result = dict(stats=stats, effective=json.loads(q.stdout), requirements=payload)
    (output/'permission-inventory.json').write_text(json.dumps(result,indent=2)+'\n')
    effective = result['effective']; access = effective['access']
    assert effective['uid'] == user.pw_uid and effective['gid'] == user.pw_gid
    assert all(access[str(p)]['x'] for p in parents), 'parent traversal denied'
    assert all(access[str(p)]['r'] and not access[str(p)]['w'] for p in reads), 'public/private read boundary'
    assert access[str(output)]['w'], 'evidence output denied'
    assert all(not access[str(p)]['w'] for p in protected), 'protected path writable'
    assert all(v in (13,1) for v in effective['negative_open_write'].values()), 'private input writable'
    # Reproduce root acknowledgment publication under the restrictive controller umask.
    temp = output/'.root-ack.tmp'
    temp.write_text('{"result":"passed"}')
    temp.chmod(0o644)
    ack = output/'.root-ack'
    temp.rename(ack)
    subprocess.run(['runuser','-u',USER,'--','python3','-c',
                    'import json,sys; assert json.load(open(sys.argv[1]))["result"]=="passed"',str(ack)],check=True)
    ack.unlink()
    return result

if __name__ == '__main__':
    inventory(sys.argv[1])
