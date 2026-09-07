#!/usr/bin/python3
"""Target-local delegation boundary tests; every request must be rejected."""
import hashlib,json,subprocess
from pathlib import Path
lun=Path('/sys/kernel/config/usb_gadget/blikvm_m5/functions/mass_storage.g4/lun.0')
image=Path('/usr/share/kvmd-msd/images/g4-storage.img')
def snapshot():
 return {'lun':{p.name:p.read_text().strip() for p in (lun/n for n in ('file','ro','cdrom','removable','nofua','inquiry_string'))},'image_sha256':hashlib.sha256(image.read_bytes()).hexdigest(),'catalog':Path('/usr/share/kvmd-msd/catalog.json').read_text()}
initial=snapshot();result={'result':'failed','before':initial,'denials':[]}
try:
 base={'operation':'attach','gadget':'blikvm_m5','function':'mass_storage.g4','lun':'lun.0','image':'g4-storage.img'}
 requests=[]
 for key,value in [('gadget','other'),('function','mass_storage.usb0'),('lun','lun.1'),('image','/dev/mmcblk0'),('image','../g4-storage.img'),('image','/etc/passwd'),('image','unknown.img'),('operation','write')]:
  r=dict(base);r[key]=value;requests.append(r)
 for key in ('rw','cdrom','path','command'):
  r=dict(base);r[key]=True;requests.append(r)
 for request in requests:
  code='''import socket,json
s=socket.socket(socket.AF_UNIX);s.settimeout(3);s.connect('/run/kvmd-msd/control.sock')
s.sendall(INPUT.encode()+b'\\n');print(s.recv(4096).decode())
'''.replace('INPUT',repr(json.dumps(request)))
  p=subprocess.run(['runuser','-u','kvmd','--','python3','-c',code],capture_output=True,text=True,timeout=8)
  assert p.returncode==0,p.stderr
  response=json.loads(p.stdout);assert response['ok'] is False,response
  result['denials'].append({'request':request,'response':response})
  assert snapshot()==initial,'state changed after rejected helper request'
 p=subprocess.run(['runuser','-u','www-data','--','python3','-c',"import socket;s=socket.socket(socket.AF_UNIX);s.connect('/run/kvmd-msd/control.sock')"],capture_output=True,text=True,timeout=5)
 assert p.returncode!=0 and 'PermissionError' in p.stderr,p.stderr
 result['unrelated_user_socket_denied']=True
 result['unit']=subprocess.check_output(['systemctl','cat','blikvm-msd-helper'],text=True)
 result['kvmd_policy']=subprocess.check_output(['systemctl','show','kvmd','-p','User','-p','NoNewPrivileges','-p','CapabilityBoundingSet','-p','ReadWritePaths'],text=True)
 result['after']=snapshot();assert result['after']==initial
 result['result']='passed'
except Exception as ex:result['error']=str(ex)
print(json.dumps(result,indent=2));raise SystemExit(result['result']!='passed')
