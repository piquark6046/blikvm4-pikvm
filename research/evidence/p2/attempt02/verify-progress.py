#!/usr/bin/env python3
"""Replay completed P2 attempt02 gates from private archives; never accept P2."""
import argparse,hashlib,json,tarfile
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('private_directory',type=Path);a=p.parse_args()
archives={
'postreboot-evidence.tar.gz':('a8a2e3bc25b046d507ef043909c937ab37c6f99ef450ec3c8e3812bad90bb326','SHA256.json',''),
'core-evidence.tar.gz':('db34f549ea7e85b964efec85566a08aa8ddf5faa07ed7ab0320aa48da25c27ca','SHA256.json',''),
'lan-hdmi-evidence.tar.gz':('4abf93c1886ebfeb2663f9776a9dd4aaa7f4e993636f2a698173d665f19252f9','archive-SHA256.json',''),
'reconnect-evidence.tar.gz':('cff3503218d483f94eb201112895aab2dc38d60d33eecb6add0907b824ce712e','archive-SHA256.json',''),
'normal-reboot-evidence.tar.gz':('65e68116534a5ba6fe6b3ba4f038c13739f0074bce42d242b9fc86043f93fbfc','snapshot/SHA256.json','snapshot/'),
}
def read(archive,name):
 with tarfile.open(a.private_directory/archive) as t:return t.extractfile(name).read()
def obj(archive,name):return json.loads(read(archive,name))
verified={}
for name,(digest,manifest,prefix) in archives.items():
 with (a.private_directory/name).open('rb') as f:assert hashlib.file_digest(f,'sha256').hexdigest()==digest
 with tarfile.open(a.private_directory/name) as t:
  members=json.load(t.extractfile(manifest))
  for member,expected in members.items():assert hashlib.sha256(t.extractfile(prefix+member).read()).hexdigest()==expected,(name,member)
 verified[name]={'sha256':digest,'verified_members':len(members)}
core=obj('core-evidence.tar.gz','core-qualified/controller-result.json');assert core['result']=='passed'
assert all(s['result']=='passed' for s in core['stages'])
msd=obj('core-evidence.tar.gz','core-qualified/browser-msd/result.json');assert msd['result']=='passed' and len(msd['stages'])==11
combined=obj('core-evidence.tar.gz','core-qualified/two-client-hid-msd/result.json');assert combined['result']=='passed' and combined['direct_reads']>=20
video=combined['hid_video']['video'];assert video['client_count']==2 and video['seconds']==120
fps=[]
for i,c in enumerate(video['clients']):
 assert c['capacity_passed'] and c['fps']>=27 and c['frames']>=3240 and c['max_gap']<=3
 frames=[json.loads(l) for l in read('core-evidence.tar.gz',f'core-qualified/two-client-hid-msd/hid-video/two-clients/client-{i}/frames.jsonl').splitlines()]
 assert len(frames)==c['frames'];assert all(len({f['sha256'] for f in frames if w*5<=f['t']<(w+1)*5})>=2 for w in range(24));fps.append(c['fps'])
ui=obj('core-evidence.tar.gz','core-qualified/browser-hid-msd/result.json');assert ui['result']=='passed' and ui['direct_reads']>=20
hdmi=obj('lan-hdmi-evidence.tar.gz','result.json');assert hdmi['result']=='passed' and hdmi['generation_before']==hdmi['generation_after']
assert len(hdmi['no_signal_snapshots'])==4 and len(set(hdmi['no_signal_snapshots']))==1
assert hdmi['after']['unique_hashes']>1 and hdmi['lan_policy']=='passed' and hdmi['privilege']=='passed'
reconnect=obj('reconnect-evidence.tar.gz','result.json');assert reconnect['result']=='passed' and not reconnect['manual_target_repair']
for stage in ['hid-api','msd-browser','hid-browser']:assert obj('reconnect-evidence.tar.gz',stage+'/result.json')['result']=='passed'
reboot=obj('normal-reboot-evidence.tar.gz','snapshot/reboot-result.json');assert reboot['result']=='passed' and reboot['full_firmware_trace']
before=obj('normal-reboot-evidence.tar.gz','snapshot/before.json');after=obj('normal-reboot-evidence.tar.gz','snapshot/after.json')
assert before['boot_id']!=after['boot_id'] and before['machine_id']==after['machine_id'] and before['host_public_keys']==after['host_public_keys']
assert before['sha256']==after['persistence_sha256'] and not after['commands']['failed_units']['stdout'].strip()
raw=read('normal-reboot-evidence.tar.gz','snapshot/uart--uart-001.raw');start=raw.index(b'U-Boot SPL');markers=[b'U-Boot SPL',b'BL31:',b'U-Boot 2021',b'/boot/boot.scr',b'Starting kernel',b'root=PARTUUID=b14b0001-01',b'systemd[1]'];positions=[raw.index(m,start) for m in markers];assert positions==sorted(positions)
post=obj('postreboot-evidence.tar.gz','postreboot-core/controller-result.json');assert post['result']=='passed' and all(x['result']=='passed' for x in post['stages'])
print(json.dumps({'result':'completed_gates_replayed','p2_accepted':False,'archives':verified,'two_client_fps':fps,'hid_cycles':len(combined['hid_video']['hid']),'combined_direct_reads':combined['direct_reads'],'browser_direct_reads':ui['direct_reads'],'physical_usb_reconnect':'passed','normal_reboot_firmware':'complete','persistence':'passed','remaining':['second cold boot and retained checks','final artifact and journal review','persistence cleanup']},indent=2))
