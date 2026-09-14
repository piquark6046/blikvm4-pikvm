#!/usr/bin/env python3
"""Read-only attached-G4 prerequisite/postcondition; never normalizes target state."""
import hashlib,json,subprocess,time
from pathlib import Path
BOOT='1c8365c7-90bf-46fb-8db4-5ec06a745a6a'
IMAGE='/usr/share/kvmd-msd/images/g4-storage.img'
SHA='14845cb5d5d773bc3b7411d2e939b948abc9a7fcc04229159f32a355777ec45b'
ATTRS={'file':IMAGE,'ro':'1','cdrom':'0','removable':'0','nofua':'0','inquiry_string':'BliKVM  G4 RAM RO       0001'}
TARGET=r'''
import json,subprocess,time
from pathlib import Path
root=Path('/sys/kernel/config/usb_gadget');g=root/'blikvm_m5';f=g/'functions/mass_storage.g4';l=f/'lun.0'
r={'boot_id':Path('/proc/sys/kernel/random/boot_id').read_text().strip(),'started_monotonic_ns':time.monotonic_ns(),'gadgets':[p.name for p in root.iterdir()],'functions':sorted(p.name for p in (g/'functions').iterdir()),'luns':sorted(p.name for p in f.glob('lun.*')),'attrs':{n:(l/n).read_text().strip() for n in ('file','ro','cdrom','removable','nofua','inquiry_string')}}
p=subprocess.run(['curl','--silent','--show-error','--fail','--unix-socket','/run/kvmd/api/kvmd.sock','http://localhost/msd'],capture_output=True,text=True,timeout=15)
r['api_returncode']=p.returncode;r['api']=json.loads(p.stdout) if p.returncode==0 else None;r['api_stderr']=p.stderr
r['finished_monotonic_ns']=time.monotonic_ns();print(json.dumps(r))
'''
def check(inv,state,host,expected_boot=BOOT):
 assert inv['boot_id']==state['boot_id']==expected_boot,'unexpected boot ID'
 assert json.loads(inv['commands']['root']['stdout'])['filesystems'][0]['source']=='/dev/mmcblk0p1','physical SD root'
 assert len(inv['hash_checks'])==10690 and all(v['matches'] and v['sha256']==v['expected'] for v in inv['hash_checks'].values()),'production hashes'
 assert not inv['commands']['failed_units']['stdout'].strip(),'failed production service'
 assert state['gadgets']==['blikvm_m5'] and state['functions']==['hid.absolute','hid.keyboard','hid.relative','mass_storage.g4'] and state['luns']==['lun.0'],'gadget topology'
 assert state['attrs']==ATTRS,'attached RO MSD prerequisite false'
 assert state['api_returncode']==0 and state['api']['ok'],'MSD API'
 a=state['api']['result'];d=a['drive']
 assert a['enabled'] and a['online'] and not a['busy'] and d['connected'] and not d['rw'] and not d['cdrom'],'MSD not connected RO'
 assert d['image']['name']=='g4-storage.img' and not d['image']['writable'] and set(a['storage']['images'])=={'g4-storage.img'},'approved selected image'
 assert host['identity']['ro']=='1' and host['identity']['size']=='16384','host RO medium'
 assert host['bytes']==8388608 and host['sha256']==SHA,'host complete image mismatch'
 return {'result':'ATTACHED_MSD_PREREQUISITE_PASS','boot_id':expected_boot,'file':IMAGE,'connected':True,'ro':1,'hashes':10690,'host_sha256':SHA,'target_mutation':False}

def collect(inv,out,G,ssh):
 out=Path(out);out.mkdir()
 p=subprocess.run(ssh+['sudo -n python3 -'],input=TARGET,capture_output=True,text=True,timeout=40)
 (out/'target-transport.json').write_text(json.dumps(dict(returncode=p.returncode,stderr=p.stderr)))
 (out/'target-state.json').write_text(p.stdout)
 assert p.returncode==0,'read-only prerequisite transport failed'
 state=json.loads(p.stdout)
 # Fail on target state before attempting host media read, and always before Chromium.
 assert state['attrs']==ATTRS and state['boot_id']==BOOT,'attached RO MSD prerequisite false before Chromium'
 assert state['api_returncode']==0 and state['api']['result']['drive']['connected'],'API prerequisite false before Chromium'
 device=G['wait_device'](True,20);identity=G['block_identity'](device)
 data=G['read_image_direct'](identity['node'])
 host={'identity':identity,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}
 (out/'host.json').write_text(json.dumps(host,indent=2))
 result=check(inv,state,host);result['finished_wall_ns']=time.time_ns()
 (out/'result.json').write_text(json.dumps(result,indent=2));return result
