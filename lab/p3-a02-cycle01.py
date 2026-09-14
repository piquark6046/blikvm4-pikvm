#!/usr/bin/env python3
"""P3-A attempt 02 connected cycle 1, reusing the accepted H5R2 browser bytes."""
import ast,hashlib,json,os,runpy,socket,ssl,subprocess,sys,time,uuid
from pathlib import Path
B=Path('/var/lib/blikvm-p3-h5r2')
F=runpy.run_path(str(B/'input/functional/lab/p3-h5r2-functional.py'))
P=F['P'];H=P['H'];require,publish,read=P['require'],P['publish'],P['read']
CTX=F['CTX'];PREP=F['PREP'];NAME='p3-a02-cycle-001';D=B/'controller'/NAME
S=runpy.run_path(str(CTX/'lab/p3-h5r2-state.py'))
G=runpy.run_path(str(CTX/'lab/storagelab.py'))
SSH=next(ast.literal_eval(n.value) for n in ast.parse((PREP/'collect.py').read_text()).body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='ssh' for t in n.targets))
FAIL=B/'controller/P3_A02_FAILED.json'

def prerequisite():
 require(not FAIL.exists(),'P3-A attempt 02 FAILED; no retry')
 require(not (B/'controller/FAILED.json').exists(),'H5R2 failed')
 require(read(B/'controller/h5r2-acceptance.json')['result']=='H5R2_INDEPENDENTLY_ACCEPTED','H5R2 acceptance missing')
 require(read(B/'controller/p3-a02-immediate/result.json')['result']=='P3_A02_IMMEDIATE_INVENTORY_PASS','immediate inventory missing')
 require(P['manifest'](B/'input')==read(B/'controller/functional-input-manifest.json'),'accepted browser inputs changed')
 P['idle']()

def inventory(label):
 p=subprocess.run(['python3',str(PREP/'collect.py'),str(D/label)],capture_output=True,text=True,timeout=300)
 publish(D/(label+'-transport.json'),dict(returncode=p.returncode,stdout=p.stdout,stderr=p.stderr))
 require(p.returncode==0,'inventory transport failed')
 return read(D/label/'target.json')

def attached(inv,label,boot):
 out=D/(label+'-msd-gate');P['mkdir'](out)
 p=subprocess.run(SSH+['sudo -n python3 -'],input=S['TARGET'],capture_output=True,text=True,timeout=40)
 publish(out/'target-transport.json',dict(returncode=p.returncode,stderr=p.stderr))
 (out/'target-state.json').write_text(p.stdout)
 require(p.returncode==0,'MSD read-only transport failed');state=json.loads(p.stdout)
 require(state['attrs']==S['ATTRS'] and state['boot_id']==boot,'postboot attached MSD invariant failed')
 require(state['api_returncode']==0 and state['api']['result']['drive']['connected'],'postboot MSD API disconnected')
 device=G['wait_device'](True,20);identity=G['block_identity'](device);data=G['read_image_direct'](identity['node'])
 host=dict(identity=identity,bytes=len(data),sha256=hashlib.sha256(data).hexdigest());publish(out/'host.json',host)
 result=S['check'](inv,state,host,expected_boot=boot);publish(out/'result.json',result)
 return result

def collect(label,boot):
 inv=inventory(label)
 runpy.run_path(str(PREP/'assess.py'))['assess'](inv,read(PREP/'p2-identity.json'))
 old=read(B/'controller/p3-a02-immediate/inventory/target.json')
 for k in ('sd_cid','machine_id','host_public_keys','hash_checks'):require(inv[k]==old[k],'accepted SD identity drift: '+k)
 require(inv['boot_id']==boot,'cycle boot changed')
 attached(inv,label,boot);return inv

def generations(inv):
 return [l for k in ('services','ssh_show') for l in inv['commands'][k]['stdout'].splitlines() if l.startswith(('Id=','InvocationID=','ExecMainStartTimestampMonotonic=','NRestarts='))]

def prepare():
 prerequisite();P['mkdir'](D)
 for name in ('p3-a02-cycle01.py','p3-a02-capture.py','source-provenance.json'):
  (D/name).write_bytes((Path(__file__).parent/name).read_bytes())
 source=read(D/'source-provenance.json')
 for name,digest in source['files'].items():require(H['digest'](D/name)==digest,'cycle source drift')
 publish(D/'prepared.json',dict(attempt=2,cycle=1,total_cycles=12,accepted_cycles=0,ethernet='connected_throughout',preparation_reboot_counted=False,source=source))

def execute():
 prerequisite();require(D.is_dir() and not (D/'cycle.json').exists(),'cycle already attempted')
 for name,digest in read(D/'source-provenance.json')['files'].items():require(H['digest'](D/name)==digest,'cycle source drift')
 c=read(B/'input/contract.json');leaf=B/'active'/(NAME+'-'+uuid.uuid4().hex)
 cycle=dict(attempt=2,cycle=1,total_cycles=12,accepted_cycles=0,result='in_progress',ethernet='connected_throughout',started_wall_ns=time.time_ns(),preparation_reboot_counted=False)
 r=dict(name=NAME,result='in_progress',qualification_credit=0,accepted_cycles=0,stages=[],leaf=str(leaf));before=None;boot=None
 publish(D/'cycle.json',cycle);publish(D/'start.json',r)
 try:
  require(Path('/sys/class/net/enp1s0/carrier').read_text().strip()=='1','Ethernet not connected')
  old=read(B/'controller/p3-a02-immediate/inventory/target.json')['boot_id'];pre=collect('preboot',old)
  events=[json.loads(l) for l in (D/'uart/events.jsonl').read_text().splitlines()]
  require(any(e['event']=='uart_open' for e in events) and not any(e['event']=='uart_unavailable' for e in events),'UART not ready')
  os.kill(read(D/'uart/ready.json')['pid'],0)
  cycle.update(before_boot_id=old,reboot_request_wall_ns=time.time_ns(),reboot_request_monotonic_ns=time.monotonic_ns());publish(D/'cycle.json',cycle)
  code="from pathlib import Path; import subprocess; assert Path('/proc/sys/kernel/random/boot_id').read_text().strip()=="+repr(old)+"; subprocess.run(['systemctl','reboot'],check=True)"
  p=subprocess.run(SSH+['sudo -n python3 -'],input=code,capture_output=True,text=True,timeout=20)
  publish(D/'reboot-request.json',dict(returncode=p.returncode,stdout=p.stdout,stderr=p.stderr));require(p.returncode in (0,255),'reboot request failed')
  ctx=ssl.create_default_context(cafile=str(CTX/'private/ca.crt'));deadline=time.monotonic()+180
  recovered=False
  with (D/'recovery.jsonl').open('x',buffering=1) as log:
   while time.monotonic()<deadline:
    item=dict(wall_ns=time.time_ns(),monotonic_ns=time.monotonic_ns())
    try:
     p=subprocess.run(SSH+['cat /proc/sys/kernel/random/boot_id'],capture_output=True,text=True,timeout=8)
     item.update(ssh_exit=p.returncode,boot_id=p.stdout.strip())
     if p.returncode==0 and p.stdout.strip()!=old:
      with socket.create_connection(('192.168.88.2',443),timeout=3) as raw:
       with ctx.wrap_socket(raw,server_hostname='blikvm-v4.lab') as tls:
        item['certificate_sha256']=hashlib.sha256(tls.getpeercert(binary_form=True)).hexdigest()
        tls.sendall(b'GET / HTTP/1.1\r\nHost: blikvm-v4.lab\r\nConnection: close\r\n\r\n');require(tls.recv(4096).split()[1]==b'302','HTTPS response')
      item['trusted_https']=True;boot=p.stdout.strip();recovered=True
    except Exception as ex:item['error']=repr(ex)
    log.write(json.dumps(item)+'\n')
    if recovered:break
    time.sleep(1)
  require(recovered,'180-second startup recovery failed')
  startup=collect('startup',boot);cycle['startup_boot_id']=boot
  raw=b''.join(p.read_bytes() for p in sorted((D/'uart').glob('uart-*.raw')))
  markers=['U-Boot SPL','BL31:','U-Boot 2021','/boot/boot.scr','Starting kernel','root=PARTUUID=b14b0001-01','systemd[1]']
  positions=[raw.find(s.encode()) for s in markers];require(all(i>=0 for i in positions) and positions==sorted(positions),'firmware chain incomplete')
  require(raw.count(b'U-Boot SPL')==1 and b'TFTP' not in raw,'unexpected extra boot or TFTP')
  cycle['firmware_markers']=dict(zip(markers,positions));publish(D/'cycle.json',cycle)
  P['mkdir'](leaf,owner=(c['uid'],c['gid']));before=P['protected']();publish(D/'protected-before.json',before)
  P['audit'](leaf,D/'before-target-audit.json');first=collect('before',boot)
  require(generations(first)==generations(startup),'startup service restart')
  publish(D/'boot-result.json',dict(run_directory='/home/user/blikvm-p2/attempt02/coldboot01',boot_id=boot,qualification_pass=False))
  for label in ('msd','hid'):
   output=leaf/label;P['mkdir'](output,owner=(c['uid'],c['gid']));P['reset_home']();control=D/label;P['mkdir'](control)
   ack=B/'input/acks'/(NAME+'-'+label);P['mkdir'](ack,0o755)
   req=P['audit'](leaf,D/(label+'-before-audit.json'));requirements=ack/'requirements.json';publish(requirements,req,0o644)
   env=dict(PATH='/usr/sbin:/usr/bin:/sbin:/bin',LANG='C.UTF-8',PYTHONDONTWRITEBYTECODE='1',P3_BROWSER_LEAF=str(output),P3_CONTROL=str(ack),P3_LAUNCH_REQUIREMENTS=str(requirements))
   with (control/'harness.log').open('x') as log:
    p=subprocess.run(['/usr/bin/python3',str(CTX/'lab'/(label+'-browser-hil.py')),'--output',str(control),'--boot-result',str(D/'boot-result.json')],cwd=CTX,env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,timeout=850,close_fds=True)
   P['idle']();result=read(control/'result.json');br=read(output/'browser-result.json');logs=(control/'browser.log').read_text();argv=[s for s in logs.splitlines() if '<launching>' in s];publish(control/'generated-argv.json',argv)
   require(len(list(output.glob('launch-*-contract.json')))==len(argv)==(2 if label=='msd' else 1),'missing contract/argv')
   require(p.returncode==0 and result['result']==br['result']=='passed' and 'SIGTRAP' not in logs,'browser smoke failed')
   P['mkdir'](output/'runtime-home')
   for f in list(P['HOME'].iterdir()):os.rename(f,output/'runtime-home'/f.name)
   require(P['protected']()==before,'protected evidence changed');r['stages'].append(dict(name=label,result='passed',launches=len(argv)))
  last=collect('after',boot);require(generations(last)==generations(first),'service generation changed')
  r.update(result='FUNCTIONAL_PASS_PENDING_VM_REPLAY',hashes_matched=10690,boot_id=boot)
  cycle.update(result='CYCLE_PASS_PENDING_INDEPENDENT_REPLAY',finished_wall_ns=time.time_ns())
 except BaseException as ex:
  r.update(result='FAILED',error=repr(ex));cycle.update(result='FAILED',error=repr(ex));publish(FAIL,cycle)
  try:inventory('failure-preservation')
  except BaseException as more:cycle['preservation_error']=repr(more)
 finally:
  try:
   r['browser_idle']=P['idle']()
   if leaf.exists():
    if list(P['HOME'].iterdir()):
     P['mkdir'](leaf/'failure-runtime-home')
     for f in list(P['HOME'].iterdir()):os.rename(f,leaf/'failure-runtime-home'/f.name)
    r['seal']=H['seal'](leaf,B);P['audit'](None,D/'after-seal-audit.json')
    after=P['protected']();publish(D/'protected-after.json',after);require(before==after and before is not None,'protected history changed')
   require(P['manifest'](B/'input')==read(B/'controller/functional-input-manifest.json'),'accepted browser inputs changed')
   r['protected_inputs_unchanged']=True
  except BaseException as ex:
   r.update(result='FAILED',preservation_error=repr(ex));cycle.update(result='FAILED',preservation_error=repr(ex))
   if not FAIL.exists():publish(FAIL,cycle)
  r['finished_ns']=time.time_ns();publish(D/'result.json',r);publish(D/'cycle.json',cycle)
 print(json.dumps(cycle));require(cycle['result']!='FAILED','P3-A stopped; no retry or repair')
if __name__=='__main__':
 require(os.geteuid()==0,'root controller required');os.umask(0o077)
 if sys.argv[1:] == ['prepare']:prepare()
 elif sys.argv[1:] == ['execute']:execute()
 else:raise SystemExit('prepare | execute')
