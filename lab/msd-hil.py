#!/usr/bin/env python3
"""M8-E authenticated LAN API and host SCSI evidence, with narrow identity guards."""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import runpy
import subprocess
import sys
import time
import urllib.request
import urllib.error

H=runpy.run_path(str(Path(__file__).with_name('hid-api-hil.py')))
G4=H['G4']
IMAGE_HASH=G4['EXPECTED']['sha256']
MEDIA='/usr/share/kvmd-msd/images/g4-storage.img'

class Harness:
    def __init__(self,output,boot):
        output=output.resolve()
        self.output=output;output.mkdir(parents=True,exist_ok=False)
        self.rec=H['Recorder'](output)
        self.client=H['Client'](Path('private').resolve())
        self.client.login()
        known=Path(json.loads(boot.read_text())['run_directory'])/'known_hosts'
        self.ssh=['ssh','-i','/home/user/.local/share/blikvm-m7/id_ed25519','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-o','UserKnownHostsFile='+str(known),'blikvm@192.168.88.2']
        self.device=G4['wait_device'](True,20)
        self.identity=G4['block_identity'](self.device)
        self.result={'result':'failed','identity':self.identity,'transitions':[]}
        H['usb_descriptors'](self.device,self.rec,'initial')
        G4['exact_descriptors'](self.device,self.rec,'initial')

    def target(self,label,code):
        p=subprocess.run(self.ssh+['sudo -n python3 -'],input=code,text=True,capture_output=True,timeout=45)
        self.rec.save_text(label+'.stdout',p.stdout);self.rec.save_text(label+'.stderr',p.stderr)
        assert p.returncode==0,label+': '+p.stderr
        return json.loads(p.stdout)

    def state(self,label,connected):
        state=self.client.request('/msd')['result']
        self.rec.save_text(label+'-api.json',json.dumps(state,indent=2))
        assert state['enabled'] and state['online'] and not state['busy'],state
        assert state['drive']['connected']==connected and not state['drive']['rw'] and not state['drive']['cdrom'],state
        assert set(state['storage']['images'])=={'g4-storage.img'}
        assert not state['storage']['images']['g4-storage.img']['writable']
        inv=self.target(label+'-target', '''import hashlib,json,runpy,subprocess
from pathlib import Path
m=runpy.run_path('/usr/lib/kvmd-msd/media-helper')
l=m['validate']();m['catalog']()
attrs={k:(l/k).read_text().strip() for k in ('file','ro','cdrom','removable','nofua','inquiry_string')}
paths=[l/x for x in ('file','forced_eject','ro','cdrom','removable')]+[Path('/usr/share/kvmd-msd/images/g4-storage.img'),Path('/dev/mmcblk0')]
permissions={str(p):subprocess.run(['runuser','-u','kvmd','--','test','-w',str(p)]).returncode for p in paths}
assert all(v!=0 for v in permissions.values()),permissions
print(json.dumps({'lun':attrs,'permissions':permissions,'hash':hashlib.sha256(Path('/usr/share/kvmd-msd/images/g4-storage.img').read_bytes()).hexdigest(),'legacy_hash':hashlib.sha256(Path('/usr/share/g4-storage.img').read_bytes()).hexdigest(),'boot_id':Path('/proc/sys/kernel/random/boot_id').read_text().strip()}))
''')
        assert inv['lun']['file']==(MEDIA if connected else ''),inv
        assert inv['hash']==inv['legacy_hash']==IMAGE_HASH
        self.result['transitions'].append({'label':label,'connected':connected,'image_sha256':inv['hash']})
        return state

    def ready(self,label):
        # A media transition is allowed exactly one UNIT ATTENTION, never an arbitrary retry pass.
        values=[]
        for i in range(2):
            p=G4['command'](self.rec,label+'-tur-'+str(i),['sg_raw',self.identity['sg'],'00','00','00','00','00','00'],check=False)
            values.append(p.returncode)
            if p.returncode==0:break
            assert i==0 and p.returncode==6 and 'Unit Attention' in p.stderr,p.stderr
        assert values[-1]==0,values

    def media(self,label):
        self.ready(label)
        value=G4['storage_test'](self.device,self.rec,label)
        assert value['passed']
        self.state(label+'-after-writes',True)
        return value

    def absent(self,label):
        self.state(label,False)
        p=G4['command'](self.rec,label+'-tur',['sg_raw',self.identity['sg'],'00','00','00','00','00','00'],check=False)
        assert p.returncode==2 and 'Medium not present' in p.stderr,p.stderr
        p=G4['command'](self.rec,label+'-read',['dd','if='+self.identity['node'],'of=/dev/null','bs=512','count=1','iflag=direct'],check=False)
        assert p.returncode!=0
        assert all(Path(self.identity[k]).exists() for k in ('node','sysfs','sg','scsi'))

    def connect(self,label):
        self.client.request('/msd/set_params',{'image':'g4-storage.img','rw':'false','cdrom':'false'})
        self.state(label+'-selected',False)
        self.client.request('/msd/set_connected',{'connected':'true'})
        self.state(label,True)
        self.media(label)

    def eject(self,label):
        self.client.request('/msd/set_connected',{'connected':'false'})
        self.absent(label)

    def deny(self,client,label,path,params,statuses):
        try:client.request(path,params)
        except urllib.error.HTTPError as ex:
            assert ex.code in statuses,(label,ex.code)
            self.result.setdefault('denials',[]).append({'label':label,'path':path,'params':params,'status':ex.code})
        else:raise AssertionError(label+' was allowed')

    def authorization(self):
        before=self.state('auth-before',True)
        unauth=H['Client'](Path('private').resolve())
        for path,params in [('/msd',None),('/msd/set_params',{'image':'g4-storage.img'}),('/msd/set_connected',{'connected':'false'})]:
            self.deny(unauth,'unauth',path,params,(401,403))
        for path in ('/msd/set_params?image=g4-storage.img','/msd/set_connected?connected=false'):
            req=urllib.request.Request('https://blikvm-v4.lab/api'+path,data=b'',headers={'Authorization':'Basic '+base64.b64encode(b'invalid:invalid').decode()})
            try:unauth.opener.open(req,timeout=10)
            except urllib.error.HTTPError as ex:assert ex.code==403,ex.code
            else:raise AssertionError('invalid credential accepted')
        for route in ('write','write_remote','remove','reset'):
            self.deny(self.client,'disabled-'+route,'/msd/'+route,{'image':'g4-storage.img','url':'http://192.168.88.1/invalid'},(404,405))
        for params in ({'rw':'true'},{'cdrom':'true'},{'image':'/dev/mmcblk0'},{'image':'../g4-storage.img'},{'image':'http://192.168.88.1/invalid'},{'path':'/etc/passwd'}):
            self.deny(self.client,'forbidden-params','/msd/set_params',params,(400,409))
        assert self.state('auth-denied-after',True)['drive']==before['drive']
        self.client.request('/auth/logout',{})
        for path,params in [('/msd',None),('/msd/set_params',{'image':'g4-storage.img'}),('/msd/set_connected',{'connected':'false'})]:
            self.deny(self.client,'logged-out',path,params,(401,403))
        self.client.login();self.state('logout-retained',True)

    def disconnected_denials(self):
        before=self.state('disconnected-negative-before',False)
        for params in ({'rw':'true'}, {'image':'g4-storage.img','rw':'true'},
                       {'cdrom':'true'}, {'image':'../g4-storage.img'},
                       {'image':'unknown.img'}, {'image':'/dev/mmcblk0'},
                       {'image':'http://192.168.88.1/invalid'}):
            self.deny(self.client,'disconnected-forbidden','/msd/set_params',params,(400,409))
        for route in ('/msd/set_params?rw=false&rw=true',
                      '/msd/set_connected?connected=true&rw=true',
                      '/msd/set_connected?connected=false&connected=true'):
            req=urllib.request.Request('https://blikvm-v4.lab/api'+route,data=b'')
            try:self.client.opener.open(req,timeout=10)
            except urllib.error.HTTPError as ex:
                assert ex.code==400,(route,ex.code)
                self.result.setdefault('denials',[]).append({'path':route,'status':ex.code})
            else:raise AssertionError('malformed query accepted')
        assert self.state('disconnected-negative-after',False)['drive']==before['drive']

    def restart(self,service,label,connected):
        self.state(label+'-before',connected)
        p=subprocess.run(self.ssh+['sudo -n systemctl restart '+service],capture_output=True,text=True,timeout=45)
        self.rec.save_text(label+'-restart.log',p.stdout+p.stderr);assert p.returncode==0
        deadline=time.monotonic()+25
        while True:
            try:self.client.login();state=self.client.request('/msd')['result'];assert state['online'];break
            except (urllib.error.URLError,AssertionError) as ex:
                self.result.setdefault("restart_readiness",[]).append({"label":label,"error":str(ex)})
                assert time.monotonic()<deadline,'restart readiness timeout'
                time.sleep(.5)
        self.state(label+'-after',connected)
        if connected:self.media(label)
        else:self.absent(label)

    def finish(self):
        self.rec.save_text('result.json',json.dumps(self.result,indent=2)+'\n')


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--boot-result',type=Path,required=True);p.add_argument('--lifecycle',action='store_true');a=p.parse_args()
    h=Harness(a.output,a.boot_result)
    try:
        if not h.client.request('/msd')['result']['drive']['connected']:h.connect('initial-api-attach')
        h.state('initial',True);h.media('initial')
        h.eject('eject');h.disconnected_denials();h.connect('connect');h.eject('second-eject');h.connect('reconnect')
        h.authorization()
        if a.lifecycle:
            for connected in (False,True):
                if not connected:h.eject('lifecycle-disconnected')
                else:h.connect('lifecycle-connected')
                for service in ('kvmd','nginx'):
                    h.restart(service,service+'-'+str(connected),connected)
            h.eject('post-lifecycle-eject');h.connect('post-lifecycle-connect')
        h.result['result']='passed'
    except Exception as ex:h.result['error']=str(ex)
    finally:h.finish()
    print(json.dumps(h.result));raise SystemExit(h.result['result']!='passed')

if __name__=='__main__':main()
