#!/usr/bin/env python3
"""Append-only private H5R1 snapshot; no launch or target operation."""
import json
import os
from pathlib import Path
import runpy
import sys
import tarfile


def main():
    P=runpy.run_path(str(Path(__file__).with_name('p3-h5r1.py')))
    B=P['BASE']; H=P['H']; P['idle'](); os.umask(0o077)
    name=sys.argv[1]
    H['require'](name.replace('-','').isalnum(), 'invalid snapshot name')
    H['require'](not list((B/'active').iterdir()), 'active leaf not sealed')
    snapshot=B/'controller'/('export-'+name);snapshot.mkdir(mode=0o700)
    roots=[B/'controller',B/'sealed']+[p for p in (B/'input').iterdir() if p.name!='runtime']
    index={}
    for root in roots:
        for p in ([root] if root.is_file() else root.rglob('*')):
            if p.is_file() and not p.is_symlink():index[str(p.relative_to(B))]=H['digest'](p)
    P['publish'](snapshot/'SHA256.json',index)
    exports=Path('/home/user/blikvm-p3-h5r1-exports')
    if not exports.exists():
        exports.mkdir(mode=0o700);os.chown(exports,1000,1000)
    dest=exports/(name+'.tar.gz')
    with dest.open('xb') as f:
        with tarfile.open(fileobj=f,mode='w:gz',dereference=False) as t:
            for root in roots:t.add(root,arcname=str(root.relative_to(B)))
        f.flush();os.fsync(f.fileno())
    dest.chmod(0o400);os.chown(dest,1000,1000)
    print(json.dumps({'archive':str(dest),'sha256':H['digest'](dest),'bytes':dest.stat().st_size,'indexed':len(index)}))


if __name__=='__main__':main()
