#!/usr/bin/env python3
"""Verify two builds, pin production boot files and reuse the existing private enrollment."""
import hashlib,pathlib,json,shutil,subprocess
r=pathlib.Path('out/m8f2'); report={}
for name in ['rootfs.tar.gz','initramfs.cpio.gz','file-diff.json']:
 a=(r/'build1'/name).read_bytes();b=(r/'build2'/name).read_bytes();assert a==b,name;report[name]={'sha256':hashlib.sha256(a).hexdigest(),'bytes':len(a),'identical':True}
(r/'reproducibility.json').write_text(json.dumps(report,indent=2)+'\n')
a=r/'build1';old=pathlib.Path('out/m8f0/uvc-candidate-02/artifacts');om=json.loads((old/'manifest.json').read_text())
for name in ['Image','linux.config','sun50i-h616-blikvm-v4.dtb']:
 b=(old/name).read_bytes();assert hashlib.sha256(b).hexdigest()==om['artifacts'][name]['sha256'];shutil.copyfile(old/name,a/name)
m={'source':{'commit':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'dirty':True},'candidate':'M8-F2 logging-only','qualification':'NOT_RUN','artifacts':{}}
for n in ['rootfs.tar.gz','initramfs.cpio.gz','Image','linux.config','sun50i-h616-blikvm-v4.dtb']:
 f=a/n;m['artifacts'][n]={'size':f.stat().st_size,'sha256':hashlib.sha256(f.read_bytes()).hexdigest()}
(a/'manifest.json').write_text(json.dumps(m,indent=2)+'\n')
private=r/'private';private.mkdir(mode=0o700);dest=private/'artifacts';dest.mkdir(mode=0o700)
for n in ['Image','linux.config','sun50i-h616-blikvm-v4.dtb']:shutil.copyfile(a/n,dest/n)
b=(a/'initramfs.cpio.gz').read_bytes()+pathlib.Path('out/kvmd-lan/private/enrollment.cpio.gz').read_bytes();assert len(b)<0x6000000
(dest/'initramfs.cpio.gz').write_bytes(b);(dest/'initramfs.cpio.gz').chmod(0o600);m['artifacts']['initramfs.cpio.gz']={'size':len(b),'sha256':hashlib.sha256(b).hexdigest()};(dest/'manifest.json').write_text(json.dumps(m,indent=2)+'\n')
for n in ['reproducibility.json']:shutil.copyfile(r/n,pathlib.Path('research/evidence/m8f2/policy-01')/n)
shutil.copyfile(a/'file-diff.json','research/evidence/m8f2/policy-01/file-diff.json')
shutil.copyfile(a/'manifest.json','research/evidence/m8f2/policy-01/public-manifest.json')
print(json.dumps(report))
