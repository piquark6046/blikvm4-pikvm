#!/usr/bin/env python3
"""Record public artifacts and refresh the separate, existing private enrollment."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

root=Path('out/kvmd-lan');a=root/'artifacts';private=root/'private'
m={'source':{'commit':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
             'dirty':bool(subprocess.check_output(['git','status','--porcelain'],text=True))},
   'parent':'ubuntu-26.04.1-kvmd-web-baseline','acceptance':{'m8c':'not_qualified'},'artifacts':{}}
for f in sorted(a.iterdir()):
    if f.is_file() and f.name not in ('manifest.json','SHA256SUMS'):
        m['artifacts'][f.name]={'name':f.name,'size':f.stat().st_size,'sha256':hashlib.sha256(f.read_bytes()).hexdigest()}
(a/'manifest.json').write_text(json.dumps(m,indent=2)+'\n')
(a/'SHA256SUMS').write_text(''.join(v['sha256']+'  '+n+'\n' for n,v in m['artifacts'].items()))
if private.exists():
    image=(a/'initramfs.cpio.gz').read_bytes()+(private/'enrollment.cpio.gz').read_bytes()
    assert len(image)<0x6000000
    digest=hashlib.sha256(image).hexdigest()
    dest=private/('artifacts-'+digest[:16]);dest.mkdir(mode=0o700,exist_ok=False)
    for n in ('Image','linux.config','sun50i-h616-blikvm-v4.dtb'):shutil.copyfile(a/n,dest/n)
    (dest/'initramfs.cpio.gz').write_bytes(image);(dest/'initramfs.cpio.gz').chmod(0o600)
    m['artifacts']['initramfs.cpio.gz']={'name':'initramfs.cpio.gz','size':len(image),'sha256':digest}
    (dest/'manifest.json').write_text(json.dumps(m,indent=2)+'\n')
    (root/'enrollment-final-public.json').write_text(json.dumps({'size':len(image),'sha256':digest,'directory':str(dest)},indent=2)+'\n')
