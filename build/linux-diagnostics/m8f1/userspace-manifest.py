#!/usr/bin/env python3
"""Hash installed /usr runtime bytes directly from the enrolled Run 03 cpio."""
import gzip,hashlib,json,stat
from pathlib import Path
p=Path('out/m8f1/artifacts/initramfs.cpio.gz')
assert hashlib.sha256(p.read_bytes()).hexdigest()=='dadf5f2839f42ae062f793a58a79afb5b2305f01e345a4c2434adbaca29467cb'
data=gzip.decompress(p.read_bytes());pos=0;files={};inodes={};entries=[]
while pos<len(data):
    h=data[pos:pos+110]
    if len(h)<110 or h[:6] not in (b'070701',b'070702'):break
    fields=[int(h[i:i+8],16) for i in range(6,110,8)]
    mode,size,namesize=fields[1],fields[6],fields[11]
    name=data[pos+110:pos+110+namesize-1].decode();pos=(pos+110+namesize+3)&~3
    payload=data[pos:pos+size];pos=(pos+size+3)&~3
    if name=='TRAILER!!!':break
    name='/'+name.removeprefix('./').lstrip('/')
    if stat.S_ISREG(mode):
        key=(fields[7],fields[8],fields[0])
        if size or fields[4]==1: inodes[key]={'sha256':hashlib.sha256(payload).hexdigest(),'bytes':size}
        if name.startswith('/usr/'): entries.append((name,key))
for name,key in entries:
    files[name]=inodes.get(key, {'sha256':hashlib.sha256(b'').hexdigest(),'bytes':0})
Path('out/m8f1/userspace-files.json').write_text(json.dumps(files,sort_keys=True)+'\n')
print(len(files),'regular /usr files')
