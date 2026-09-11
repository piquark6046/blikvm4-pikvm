#!/usr/bin/env python3
"""Finalize an immutable private retention archive after the controller exits."""
import argparse,hashlib,json,os,subprocess,tarfile,time
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('root',type=Path);a=p.parse_args();root=a.root.resolve()
while not (root/'result.json').exists():time.sleep(30)
files=[]
for f in sorted(root.rglob('*')):
 if f.is_file() and not f.is_symlink():
  with f.open('rb') as s:d=hashlib.file_digest(s,'sha256').hexdigest()
  files.append({'path':str(f.relative_to(root)),'bytes':f.stat().st_size,'sha256':d})
index=root.with_name(root.name+'-files.json');index.write_text(json.dumps(files,indent=2)+'\n')
archive=root.with_name(root.name+'-private.tar.gz')
with tarfile.open(archive,'x:gz') as t:
 for f in files:t.add(root/f['path'],arcname=root.name+'/'+f['path'],recursive=False)
 t.add(index,arcname='files.json')
with archive.open('rb') as s:d=hashlib.file_digest(s,'sha256').hexdigest()
receipt=root.with_name(root.name+'-archive.json');receipt.write_text(json.dumps({'files':len(files),'bytes':archive.stat().st_size,'sha256':d,'private':True,'controller_result':json.loads((root/'result.json').read_text())['result'],'qualification_seconds':0,'m8f':'OPEN','p1':'GATED'},indent=2)+'\n')
for f in [archive,index,receipt]:os.chown(f,1000,1000);f.chmod(0o400)
subprocess.run(['chattr','+i',str(archive),str(index),str(receipt)],check=True)
