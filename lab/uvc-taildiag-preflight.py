#!/usr/bin/env python3
"""Bridge wrapper: bounded kernel collector plus hardened ARM64 preflight."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import time

HERE=Path(__file__).resolve().parent

def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True)
    p.add_argument('--boot-result',type=Path,required=True);p.add_argument('--schema',type=Path,required=True)
    p.add_argument('--binary-sha256',required=True);a=p.parse_args()
    os.umask(0o077);out=a.output.resolve();out.mkdir(exist_ok=False)
    known=Path(json.loads(a.boot_result.read_text())['run_directory']).resolve()/'known_hosts'
    ssh=['ssh','-i','/home/user/.local/share/blikvm-m7/id_ed25519','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes',
         '-o','UserKnownHostsFile='+str(known),'-o','ConnectTimeout=10','blikvm@192.168.88.2']
    def remote(label,code):
        r=subprocess.run(ssh+['sudo -n python3 -'],input=code.encode(),capture_output=True,timeout=40)
        (out/(label+'.stdout')).write_bytes(r.stdout);(out/(label+'.stderr')).write_bytes(r.stderr)
        assert r.returncode==0,label
        return r.stdout
    result={'result':'failed','qualification':'NOT_RUN'}
    try:
        script=(HERE/'uvc-taildiag-read.py').read_text();schema=a.schema.read_text()
        remote('start',f'''from pathlib import Path
import subprocess
root=Path('/run/uvc-taildiag');root.mkdir(mode=0o700,exist_ok=False)
(root/'collector.py').write_text({script!r})
(root/'schema.json').write_text({schema!r})
if not Path('/sys/kernel/debug/usb/uvcvideo').exists():subprocess.run(['mount','-t','debugfs','debugfs','/sys/kernel/debug'],check=True)
subprocess.run(['systemd-run','--unit=m8f0-kernel-collector','--property=RuntimeMaxSec=480','python3',str(root/'collector.py'),'--schema',str(root/'schema.json'),'--output',str(root/'events'),'--seconds','450','--stop-file',str(root/'stop')],check=True)
print(subprocess.check_output(['uname','-a'],text=True))
''')
        with (out/'userspace.stdout').open('wb') as o,(out/'userspace.stderr').open('wb') as e:
            r=subprocess.run([sys.executable,str(HERE/'mjpeg-taildiag-preflight.py'),'--output',str(out/'userspace'),
                '--boot-result',str(a.boot_result.resolve()),'--binary-sha256',a.binary_sha256,'--seconds','300'],stdout=o,stderr=e,timeout=420)
        result['userspace_exit']=r.returncode
    except Exception as ex:result['error']=str(ex)
    finally:
        try:
            remote('drain',"from pathlib import Path; Path('/run/uvc-taildiag/stop').touch()")
            remote('wait',"""from pathlib import Path
import time
p=Path('/run/uvc-taildiag/events/result.json');deadline=time.monotonic()+15
while not p.exists():
 assert time.monotonic()<deadline,'kernel collector failed to drain'
 time.sleep(.1)
print(p.read_text())
""")
            blob=remote('archive',"import subprocess,sys; sys.stdout.buffer.write(subprocess.check_output(['tar','-C','/run/uvc-taildiag','-cf','-','.']))")
            archive=out/'kernel.tar';archive.write_bytes(blob)
            root=out/'kernel';root.mkdir()
            with tarfile.open(archive) as t:t.extractall(root,filter='data')
            kernel=json.loads((root/'events/result.json').read_text());state=kernel['state']
            assert kernel['result']=='collected'
            assert state['suppressed']==state['required_lost']==state['oversized']==0
            assert state['suspicious']==state['admitted']==state['acknowledged']==kernel['events']
            assert state['packets_seen']==state['packets_written']
            assert state['memory_bytes']<48*1024*1024
            assert not list(root.rglob('*.partial'))
            userspace=json.loads((out/'userspace/result.json').read_text())
            assert userspace['result']=='pending_independent_vm_review'
            result.update(result='pending_independent_vm_review',kernel=kernel,userspace=userspace,
                          kernel_archive_sha256=hashlib.sha256(blob).hexdigest())
        except Exception as ex:result['kernel_review_error']=str(ex)
        (out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result));return result['result']=='pending_independent_vm_review'

if __name__=='__main__':raise SystemExit(not main())
