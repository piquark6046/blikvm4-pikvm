#!/usr/bin/env python3
"""Export only explicit non-secret qualification roots; never enrollment images."""
import argparse
import hashlib
import json
from pathlib import Path
import tarfile

p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
a=p.parse_args();root=a.root.resolve()
assert not a.output.exists()
allowed=[]
for folder in ('runs','qualification','series','lab','build/kvmd-lan'):
    for path in sorted((root/folder).rglob('*')):
        if not path.is_file() or path.is_symlink():continue
        if '__pycache__' in path.parts:continue
        assert path.name not in ('credentials.json','htpasswd','server.key','ca.key','initramfs.cpio.gz')
        assert path.suffix not in ('.key','.cpio')
        allowed.append(path)
with tarfile.open(a.output,'w:gz') as archive:
    for path in allowed:archive.add(path,arcname=str(path.relative_to(root)),recursive=False)
print(json.dumps({'file':a.output.name,'bytes':a.output.stat().st_size,
                  'sha256':hashlib.file_digest(a.output.open('rb'),'sha256').hexdigest(),
                  'files':len(allowed),'included_roots':['runs','qualification','series','lab','build/kvmd-lan']}))
