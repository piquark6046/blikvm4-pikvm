#!/usr/bin/env python3
"""P3-S0 bridge collector: target reads only; new private evidence directory."""
import ast, hashlib, json, os, subprocess, sys, time
from pathlib import Path
BASE=Path('/var/lib/blikvm-p3-h5r1/controller/functional-preparation')
OUT=Path(sys.argv[1])
os.umask(0o077)
OUT.mkdir(parents=True,exist_ok=False)
def save(name,value):
    (OUT/name).write_text(json.dumps(value,indent=2)+'\n')
def cmd(argv,timeout=60,**kw):
    try:p=subprocess.run(argv,capture_output=True,text=True,timeout=timeout,**kw)
    except OSError as e:return dict(argv=argv,returncode=None,error=str(e))
    return dict(argv=argv,returncode=p.returncode,stdout=p.stdout,stderr=p.stderr)
ssh=next(ast.literal_eval(n.value) for n in ast.parse((BASE/'collect.py').read_text()).body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='ssh' for t in n.targets))
save('metadata.json',dict(scope='P3-S0 read-only runtime snapshot',started_ns=time.time_ns(),qualification_credit=0,source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()))
p=cmd(['python3',str(BASE/'collect.py'),str(OUT/'inventory')],timeout=300)
save('inventory-transport.json',p)
assert p['returncode']==0
code=r'''
import hashlib,json,os,subprocess,time
from pathlib import Path
r={'started_wall_ns':time.time_ns(),'started_monotonic_ns':time.monotonic_ns(),'boot_id':Path('/proc/sys/kernel/random/boot_id').read_text().strip(),'uptime':Path('/proc/uptime').read_text(),'gadget':{},'files':{},'commands':{}}
g=Path('/sys/kernel/config/usb_gadget')
for root,dirs,files in os.walk(g,followlinks=False):
 for name in dirs+files:
  p=Path(root)/name;k=str(p.relative_to(g))
  if p.is_symlink():r['gadget'][k]={'link':os.readlink(p)}
  elif p.is_dir():r['gadget'][k]={'directory':True}
  else:
   try:r['gadget'][k]={'hex':p.read_bytes().hex()}
   except OSError as e:r['gadget'][k]={'errno':e.errno,'error':str(e)}
for name in ['/usr/share/kvmd-msd/catalog.json','/usr/bin/gadget-storage','/usr/sbin/gadget-storage','/usr/lib/kvmd-msd/media-helper','/usr/share/g4-storage.sha256']:
 p=Path(name)
 if p.is_file():r['files'][name]={'text':p.read_text(),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
for name in ['/usr/share/g4-storage.img','/usr/share/kvmd-msd/images/g4-storage.img']:
 p=Path(name);r['files'][name]={'size':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'mode':oct(p.stat().st_mode),'uid':p.stat().st_uid,'gid':p.stat().st_gid}
commands={'units':['systemctl','cat','blikvm-gadget','blikvm-msd-helper','kvmd'],'status':['systemctl','status','blikvm-gadget','blikvm-msd-helper','kvmd','--no-pager','-l'],'api':['curl','--silent','--show-error','--fail','--unix-socket','/run/kvmd/api/kvmd.sock','http://localhost/msd'],'journal':['journalctl','-b','--no-pager','-o','json']}
for name,argv in commands.items():
 p=subprocess.run(argv,capture_output=True,text=True,timeout=40);r['commands'][name]={'returncode':p.returncode,'stdout':p.stdout,'stderr':p.stderr}
r['finished_wall_ns']=time.time_ns();r['finished_monotonic_ns']=time.monotonic_ns()
print(json.dumps(r))
'''
p=cmd(ssh+['sudo -n python3 -'],input=code,timeout=180)
(OUT/'target-extra-source.py').write_text(code)
save('extra-transport.json',dict(returncode=p['returncode'],stderr=p['stderr']))
assert p['returncode']==0
save('target-extra.json',json.loads(p['stdout']))
commands={'usb':['lsusb'],'usb_tree':['lsusb','-t'],'descriptors':['lsusb','-v','-d','1d6b:0106'],'blocks':['lsblk','-J','-b','-o','NAME,PATH,TYPE,SIZE,RO,MODEL,SERIAL,TRAN,HCTL,MOUNTPOINTS'],'scsi':['lsscsi','-g'],'journal':['journalctl','-b','-k','--no-pager','-o','json']}
for name,argv in commands.items():save('host-'+name+'.json',cmd(argv))
objects=[]
for p in Path('/sys/class/block').iterdir():
 resolved=str(p.resolve())
 if '/usb' not in resolved:continue
 attrs={}
 for n in ('size','ro','device/vendor','device/model','device/rev','device/state'):
  q=p/n
  if q.is_file():attrs[n]=q.read_text()
 objects.append(dict(name=p.name,sysfs=resolved,attrs=attrs))
save('host-storage-objects.json',objects)
# Only the exact BliKVM G4 object may be read. No WRITE commands in this collector.
for o in objects:
 if o['attrs'].get('device/vendor','').strip()!='BliKVM' or o['attrs'].get('device/model','').strip()!='G4 RAM RO':continue
 dev='/dev/'+o['name'];save('host-media-read.json',cmd(['dd','if='+dev,'of=/dev/null','bs=512','count=1','iflag=direct']))
 if int(o['attrs']['size'])==16384:
  # Full direct read hashed via subprocess bytes, with no persistent host cache.
  p=subprocess.run(['dd','if='+dev,'bs=512','count=16384','iflag=direct','status=none'],capture_output=True,timeout=60)
  save('host-media-hash.json',dict(returncode=p.returncode,bytes=len(p.stdout),sha256=hashlib.sha256(p.stdout).hexdigest(),stderr=p.stderr.decode()))
(OUT/'collector.py').write_bytes(Path(__file__).read_bytes())
save('complete.json',dict(finished_ns=time.time_ns(),target_mutation=False))
print(json.dumps({'snapshot':str(OUT),'complete':True}))
