#!/usr/bin/env python3
"""Overlay only the logging policy on the pinned, public M8-E rootfs archive."""
import argparse,copy,gzip,hashlib,io,json,pathlib,tarfile
p=argparse.ArgumentParser();p.add_argument('--output',type=pathlib.Path,required=True);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
base=pathlib.Path('out/kvmd-msd/artifacts/rootfs.tar.gz');policy=pathlib.Path('build/logging/zz-blikvm-bounded.conf').read_bytes();epoch=1788652800
sha=lambda b:hashlib.sha256(b).hexdigest()
assert sha(base.read_bytes())=='563ed45f6705657b8a52f97e2c5a408c182a5dc5fe9b32ac5af4cdb2d7b97f0a'
entries={};diff=[]
with tarfile.open(base) as src:
 for m in src:
  data=src.extractfile(m).read() if m.isfile() else None
  if m.name=='./etc/kvmd/nginx/nginx.conf':
   old=data;assert old.count(b'error_log /var/log/nginx/error.log warn;')==1 and old.count(b'access_log /var/log/nginx/access.log combined;')==1
   data=old.replace(b'error_log /var/log/nginx/error.log warn;',b'error_log stderr warn;').replace(b'access_log /var/log/nginx/access.log combined;',b'access_log off;');m.size=len(data)
   diff.append({'path':m.name,'before_sha256':sha(old),'after_sha256':sha(data)})
  entries[m.name]=(copy.copy(m),data)
name='./etc/systemd/journald.conf.d';assert name not in entries
m=tarfile.TarInfo(name);m.type=tarfile.DIRTYPE;m.mode=0o755;m.mtime=epoch;entries[name]=(m,None)
name+='/zz-blikvm-bounded.conf';m=tarfile.TarInfo(name);m.mode=0o644;m.mtime=epoch;m.size=len(policy);entries[name]=(m,policy);diff.append({'path':name,'before_sha256':None,'after_sha256':sha(policy)})
with (a.output/'rootfs.tar.gz').open('wb') as f,gzip.GzipFile(filename='',mode='wb',fileobj=f,mtime=0,compresslevel=9) as gz,tarfile.open(fileobj=gz,mode='w|',format=tarfile.GNU_FORMAT) as dest:
 for name,(m,data) in sorted(entries.items()):dest.addfile(m,io.BytesIO(data) if data is not None else None)
# Verify independently reopened archive: every existing member and metadata unchanged except allowed nginx bytes/size.
with tarfile.open(base) as b,tarfile.open(a.output/'rootfs.tar.gz') as c:
 bm={m.name:m for m in b};cm={m.name:m for m in c};assert set(cm)-set(bm)=={'./etc/systemd/journald.conf.d','./etc/systemd/journald.conf.d/zz-blikvm-bounded.conf'};assert not set(bm)-set(cm)
 for n,m in bm.items():
  z=cm[n]
  for field in ['mode','uid','gid','mtime','type','linkname','uname','gname','devmajor','devminor']:assert getattr(m,field)==getattr(z,field),(n,field)
  if m.isfile() and n!='./etc/kvmd/nginx/nginx.conf':assert b.extractfile(m).read()==c.extractfile(z).read(),n
(a.output/'file-diff.json').write_text(json.dumps({'base_rootfs_sha256':sha(base.read_bytes()),'changed_regular_files':diff,'added_directories':['./etc/systemd/journald.conf.d'],'all_other_payload_and_metadata_identical':True,'packages_identical':True},indent=2)+'\n')
print(a.output)
