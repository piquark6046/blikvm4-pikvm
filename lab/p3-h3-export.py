#!/usr/bin/env python3
"""Export a private append-only H3 evidence snapshot for independent VM replay."""
import hashlib
import json
import os
from pathlib import Path
import runpy
import shutil
import subprocess
import sys
import tarfile

H=runpy.run_path(str(Path(__file__).with_name('p3-h3-boundary.py')))
BASE=H['BASE'];name=sys.argv[1]
H['require'](name.replace('-','').isalnum(),'invalid export name');H['browser_idle']();os.umask(0o077)
exports=Path('/home/user/blikvm-p3-h3-exports')
if not exports.exists():
    exports.mkdir(mode=0o700);os.chown(exports,1000,1000)
snapshot=BASE/'controller'/('snapshot-'+name);snapshot.mkdir(mode=0o700)
for p in Path(__file__).parent.glob('p3-h[23]-*.py'):
    if p.is_file():shutil.copyfile(p,snapshot/p.name)
for unit in ('prepare','permission'):
    (snapshot/(unit+'-journal.log')).write_bytes(subprocess.check_output(['journalctl','-u','blikvm-p3-h3-'+unit,'--no-pager','-o','short-monotonic']))
context=snapshot/'context';context.mkdir(mode=0o700)
for p in (BASE/'input/context/lab').iterdir():
    if p.is_file():shutil.copyfile(p,context/p.name)
index={}
roots=[BASE/'controller',BASE/'sealed',BASE/'input/acks']
for root in roots:
    for p in root.rglob('*'):
        if p.is_file():index[str(p.relative_to(BASE))]=H['digest'](p)
H['publish'](snapshot/'SHA256.json',index)
archive=exports/(name+'.tar.gz')
with archive.open('xb') as f:
    with tarfile.open(fileobj=f,mode='w:gz',dereference=False) as t:
        for root in roots:t.add(root,arcname=str(root.relative_to(BASE)))
    f.flush();os.fsync(f.fileno())
archive.chmod(0o400);os.chown(archive,1000,1000)
print(json.dumps({'archive':str(archive),'sha256':H['digest'](archive),'bytes':archive.stat().st_size,'indexed':len(index)}))
