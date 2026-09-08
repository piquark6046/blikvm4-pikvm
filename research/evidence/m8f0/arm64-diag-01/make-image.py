import hashlib,json,os,shutil,subprocess,tarfile
from pathlib import Path
base=Path('/home/user/repos/blikvm4-pikvm'); work=base/'out/m8f0/arm64-diag-01'; art=work/'artifacts'; root=work/'ram-root-v2'; image=work/'ram-artifacts-v2'
os.umask(0o077)
def sha(p):return hashlib.file_digest(p.open('rb'),'sha256').hexdigest()
production=base/'out/kvmd-msd/artifacts'
assert sha(production/'rootfs.tar.gz')=='563ed45f6705657b8a52f97e2c5a408c182a5dc5fe9b32ac5af4cdb2d7b97f0a'
assert sha(base/'out/ustreamer/artifacts/ustreamer_6.65-1blikvm2_arm64.deb')=='bc8f5358a955d65fe30641a9a4012e2044c4765086093dccd509e7575038b0a1'
root.mkdir(exist_ok=False);image.mkdir(exist_ok=False)
subprocess.run(['tar','--numeric-owner','-xpf',str(production/'rootfs.tar.gz'),'-C',str(root)],check=True)
def tree():
 return {str(p.relative_to(root)):sha(p) if p.is_file() and not p.is_symlink() else ('link:'+str(p.readlink()) if p.is_symlink() else 'directory') for p in sorted(root.rglob('*'))}
before=tree(); assert before['usr/bin/ustreamer']=='e5a489c828299bc28de71789414312510198c6d7da63b2b18c300bef6313e71b'
pkg=work/'complete-package-v2';subprocess.run(['dpkg-deb','-R',str(base/'out/ustreamer/artifacts/ustreamer_6.65-1blikvm2_arm64.deb'),str(pkg)],check=True)
shutil.copyfile(art/'ustreamer',pkg/'usr/bin/ustreamer')
control=pkg/'DEBIAN/control';text=control.read_text().replace('Version: 6.65-1blikvm2\n','Version: 6.65-1blikvm2+taildiag1\n').replace('Depends: ','Depends: libssl3t64, ').replace('Description: ','Description: DIAGNOSTIC ONLY: ');control.write_text(text)
manifest=json.loads((work/'source/diagnostic-source-manifest.json').read_text());manifest.update(package_version='6.65-1blikvm2+taildiag1',binary_sha256=sha(art/'ustreamer'),base_rootfs_sha256=sha(production/'rootfs.tar.gz'),builder_image='sha256:4b424588fc99a71195dc54659ea19c77508a7d457b15cdf5101b23551fbabcbc',build_packages_sha256=sha(art/'build-packages.tsv'),branch='A',qualification='NOT_RUN')
(pkg/'usr/share/doc/ustreamer/taildiag.json').write_text(json.dumps(manifest,indent=2)+'\n')
for p in pkg.rglob('*'):os.utime(p,(1788652800,1788652800),follow_symlinks=False)
package=art/'ustreamer_6.65-1blikvm2+taildiag1-complete-v2_arm64.deb'
subprocess.run(['dpkg-deb','--root-owner-group','-Zgzip','-z9','--build',str(pkg),str(package)],check=True)
# Stage the data delta only; all inherited maintainer scripts and service files remain unchanged.
shutil.copyfile(pkg/'usr/bin/ustreamer',root/'usr/bin/ustreamer')
shutil.copyfile(pkg/'usr/share/doc/ustreamer/taildiag.json',root/'usr/share/doc/ustreamer/taildiag.json')
status=root/'var/lib/dpkg/status'; stanzas=status.read_text().split('\n\n');found=False
for i,s in enumerate(stanzas):
 if s.startswith('Package: ustreamer\n'):
  stanzas[i]=s.replace('Version: 6.65-1blikvm2\n','Version: 6.65-1blikvm2+taildiag1\n').replace('Depends: ','Depends: libssl3t64, ');found=True
assert found;status.write_text('\n\n'.join(stanzas))
assert 'Package: libssl3t64\n' in status.read_text()
drop=root/'etc/systemd/system/kvmd.service.d/90-taildiag.conf';drop.parent.mkdir(exist_ok=True)
drop.write_text('[Service]\nEnvironment=USTREAMER_TAILDIAG_DIR=/var/lib/ustreamer-taildiag\nStateDirectory=ustreamer-taildiag\nStateDirectoryMode=0700\n')
after=tree();changed={p:{'before':before.get(p),'after':after.get(p)} for p in sorted(before.keys()|after.keys()) if before.get(p)!=after.get(p)}
assert set(changed)<= {'usr/bin/ustreamer','usr/share/doc/ustreamer/taildiag.json','var/lib/dpkg/status','etc/systemd/system/kvmd.service.d','etc/systemd/system/kvmd.service.d/90-taildiag.conf'},changed
(work/'rootfs-delta.json').write_text(json.dumps(changed,indent=2)+'\n')
for p in root.rglob('*'):os.utime(p,(1788652800,1788652800),follow_symlinks=False)
with (image/'initramfs.cpio.gz').open('wb') as f:
 subprocess.run(['bash','-o','pipefail','-c','find . -xdev -print0 | LC_ALL=C sort -z | cpio --null -o -H newc --reproducible 2>/dev/null | gzip -n -9'],cwd=root,stdout=f,check=True)
with (image/'initramfs.cpio.gz').open('ab') as f:f.write((base/'out/kvmd-lan/private/enrollment.cpio.gz').read_bytes())
assert (image/'initramfs.cpio.gz').stat().st_size<0x6000000
for n in ('Image','sun50i-h616-blikvm-v4.dtb','linux.config'):shutil.copyfile(production/n,image/n);assert sha(image/n)==sha(production/n)
m={'source':{'commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=base,text=True).strip(),'dirty':True},'diagnostic_only':True,'qualification':'NOT_RUN','diagnostic':manifest,'artifacts':{p.name:{'name':p.name,'sha256':sha(p),'size':p.stat().st_size} for p in sorted(image.iterdir())}}
(image/'manifest.json').write_text(json.dumps(m,indent=2)+'\n')
(art/'final-artifact-hashes.json').write_text(json.dumps({'package':{'path':package.name,'size':package.stat().st_size,'sha256':sha(package)},'binary_sha256':sha(art/'ustreamer'),'ram_image':m['artifacts']['initramfs.cpio.gz']},indent=2)+'\n')
subprocess.run(['chown','-R','1000:1000',str(image),str(art),str(work/'rootfs-delta.json')],check=True)
print(json.dumps(m,indent=2))
