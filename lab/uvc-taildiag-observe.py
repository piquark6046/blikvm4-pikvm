#!/usr/bin/env python3
"""Bridge-only bounded cross-layer observation; never qualification."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time

HERE=Path(__file__).resolve().parent

def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True)
    p.add_argument('--boot-result',type=Path,required=True);p.add_argument('--schema',type=Path,required=True)
    p.add_argument('--seconds',type=int,default=900);a=p.parse_args();assert 1<=a.seconds<=900
    os.umask(0o077);out=a.output.resolve();out.mkdir(exist_ok=False)
    tag=out.name
    assert tag.replace('-', '').replace('_', '').isalnum()
    target_root='/run/uvc-taildiag-'+tag
    known=Path(json.loads(a.boot_result.read_text())['run_directory']).resolve()/'known_hosts'
    ssh=['ssh','-i','/home/user/.local/share/blikvm-m7/id_ed25519','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-o','UserKnownHostsFile='+str(known),'-o','ConnectTimeout=10','blikvm@192.168.88.2']
    def remote(label,code):
        r=subprocess.run(ssh+['sudo -n python3 -'],input=code.encode(),capture_output=True,timeout=45)
        (out/(label+'.stdout')).write_bytes(r.stdout);(out/(label+'.stderr')).write_bytes(r.stderr)
        assert r.returncode==0,label
        return r.stdout
    def sample(label):
        code="__name__='sample'\n"+(HERE/'mjpeg-taildiag-runtime.py').read_text()+"\nprint(json.dumps(sample(True)))\n"
        return json.loads(remote(label,code))
    result={'result':'failed','qualification':'NOT_RUN','maximum_seconds':a.seconds};process=None
    try:
        remote('prepare',f'''from pathlib import Path
import subprocess,os,json
assert subprocess.run(['systemctl','is-active','--quiet','kvmd.service']).returncode!=0
old=Path('/var/lib/ustreamer-taildiag');new=Path('/var/lib/ustreamer-taildiag-before-{tag}');assert not new.exists()
s=old.stat();old.rename(new);old.mkdir(mode=0o700);os.chown(old,s.st_uid,s.st_gid)
r=Path({target_root!r});r.mkdir(mode=0o700)
(r/'collector.py').write_text({(HERE/'uvc-taildiag-read.py').read_text()!r})
(r/'schema.json').write_text({a.schema.read_text()!r})
subprocess.run(['systemd-run','--unit=m8f0-kernel-{tag}','--property=RuntimeMaxSec=1020','python3',str(r/'collector.py'),'--schema',str(r/'schema.json'),'--output',str(r/'events'),'--seconds','990','--stop-file',str(r/'stop')],check=True)
subprocess.run(['systemctl','start','kvmd.service'],check=True)
import time
end=time.monotonic()+30
while True:
 q=subprocess.run(['curl','--max-time','2','-s','-o','/dev/null','-w','%{{http_code}}','--unix-socket','/run/kvmd/api/kvmd.sock','http://localhost/info'],capture_output=True)
 if q.returncode==0 and q.stdout in (b'200',b'401',b'403'):break
 assert time.monotonic()<end,'kvmd API readiness deadline'
 time.sleep(.25)
''')
        with (out/'observer.stdout').open('wb') as o,(out/'observer.stderr').open('wb') as e:
            process=subprocess.Popen([sys.executable,str(HERE/'mjpeg-observe-run.py'),'--output',str(out/'video'),'--known-hosts',str(known),'--private-dir',str(Path('private').resolve()),'--seconds',str(a.seconds),'--stop-file',str(out/'stop')],stdout=o,stderr=e)
        deadline=time.monotonic()+a.seconds;started=time.monotonic();i=0
        while time.monotonic()<deadline and process.poll() is None:
            info=json.loads(remote(f'poll-{i:03d}',"target_root="+repr(target_root)+"\n"+"""import json
from pathlib import Path
r=Path(target_root)/'events'
state=list(Path('/sys/kernel/debug/usb/uvcvideo').glob('*/taildiag-state'))[0].read_text()
reports=[json.loads(p.read_text()) for p in r.glob('event-*/decoded.json')]
u=[json.loads(p.read_text()) for p in Path('/var/lib/ustreamer-taildiag').glob('dqbuf-*.json')]
hashes={x['jpeg']['sha256'] for x in u}
print(json.dumps({'state':state,'collector_result':json.loads((r/'result.json').read_text()) if (r/'result.json').exists() else None,'useful':[{'id':x['header']['id'],'sha256':x['complete_sha256']} for x in reports if not x['evidence_gaps'] and x['complete_sha256'] in hashes]}))
"""));i+=1
            assert info['collector_result'] is None,'collector exited before stop'
            state={k:int(v) for k,v in (x.split('=') for x in info['state'].split())}
            assert state['suppressed']==state['required_lost']==state['oversized']==0
            if info['useful']:
                result['recurrence']=info['useful'];result['stop_reason']='useful_recurrence';break
            time.sleep(2)
        assert process.poll() in (None,0),'observer exited before recurrence or deadline'
        result.setdefault('stop_reason','bounded_deadline')
        (out/'stop').touch();process.wait(timeout=35);assert process.returncode==0
        result['elapsed_seconds']=time.monotonic()-started
        result['flush']=sample('final-flush')['ustreamer']['flush_acknowledgement']
        result['result']='pending_independent_vm_review'
    except Exception as ex:result['error']=str(ex)
    finally:
        if process and process.poll() is None:
            (out/'stop').touch()
            try:process.wait(timeout=35)
            except subprocess.TimeoutExpired:process.terminate();process.wait(timeout=10);result['forced_stop']=True
        try:
            remote('stop',"target_root="+repr(target_root)+"\nimport subprocess;subprocess.run(['systemctl','stop','kvmd.service'],check=True);from pathlib import Path;(Path(target_root)/'stop').touch()")
            remote('drain',"target_root="+repr(target_root)+"\n"+"""from pathlib import Path
import time,subprocess,json,sys
r=Path(target_root)/'events/result.json';end=time.monotonic()+15
while not r.exists():
 assert time.monotonic()<end
 time.sleep(.1)
print(r.read_text())
""")
            remote('dmesg',"import subprocess,sys;sys.stdout.buffer.write(subprocess.check_output(['dmesg']))")
            (out/'target.tar').write_bytes(remote('archive',"target_root="+repr(target_root)+"\nimport subprocess,sys;sys.stdout.buffer.write(subprocess.check_output(['tar','-cf','-','-C','/run',target_root.split('/')[-1],'-C','/var/lib','ustreamer-taildiag']))"))
        except Exception as ex:result['archive_error']=str(ex);result['result']='failed'
        (out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result));return result['result']=='pending_independent_vm_review'

if __name__=='__main__':raise SystemExit(not main())
