import gzip,pathlib,json,stat,hashlib

def read(p):
 b=gzip.decompress(pathlib.Path(p).read_bytes());i=0;d={};contents={}
 while True:
  assert b[i:i+6]==b'070701';h=[int(b[i+6+x*8:i+14+x*8],16) for x in range(13)];i+=110;name=b[i:i+h[11]-1].decode().removeprefix('./');i=(i+h[11]+3)&~3;data=b[i:i+h[6]];i=(i+h[6]+3)&~3
  if name=='TRAILER!!!':break
  d[name]=(h,data)
  if stat.S_ISREG(h[1]) and data:contents[h[0]]=data
 for n,(h,data) in d.items():
  if stat.S_ISREG(h[1]) and h[4]>1:d[n]=(h,contents.get(h[0],b''))
 return d
a=read('out/kvmd-msd/artifacts/initramfs.cpio.gz');b=read('out/m8f2/build1/initramfs.cpio.gz');changes=[]
for n,(h,data) in a.items():
 z,new=b[n]
 assert all(h[i]==z[i] for i in [1,2,3,5,9,10]),n
 if data!=new:changes.append(n)
assert changes==['etc/kvmd/nginx/nginx.conf'],changes
assert set(b)-set(a)=={'etc/systemd/journald.conf.d','etc/systemd/journald.conf.d/zz-blikvm-bounded.conf'}
p=pathlib.Path('research/evidence/m8f2/policy-01/cpio-diff.json');p.write_text(json.dumps({'result':'passed','existing_entries_checked':len(a),'changed_payloads':changes,'new_entries':sorted(set(b)-set(a)),'all_existing_modes_owners_mtimes_devices_identical':True},indent=2)+'\n');print(p.read_text())
