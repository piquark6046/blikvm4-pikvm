#!/usr/bin/env python3
"""Read-only diagnostic identity sample; --flush requests only a ring snapshot."""
import argparse
import hashlib
import json
import os
import uuid
from pathlib import Path
import subprocess
import time


def request_flush(directory, uid, gid, timeout=5):
    """Create as the verified service UID, then require atomic correlated output."""
    nonce=uuid.uuid4().hex
    child=os.fork()
    if child==0:
        try:
            if os.geteuid()==0:
                os.setgroups([]);os.setgid(gid);os.setuid(uid)
            assert os.getuid()==uid and os.geteuid()==uid
            temporary=directory/('flush-'+nonce+'.request.partial')
            fd=os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
            with os.fdopen(fd,'w') as f:f.write(nonce)
            os.link(temporary,directory/'flush.request');temporary.unlink()
            os._exit(0)
        except BaseException:
            os._exit(1)
    _,status=os.waitpid(child,0)
    assert status==0,'flush request creation failed'
    deadline=time.monotonic()+timeout
    ack=directory/('flush-'+nonce+'.json')
    while not ack.exists():
        if time.monotonic()>=deadline:
            raise TimeoutError('missing flush acknowledgement: '+nonce)
        time.sleep(.05)
    result=json.loads(ack.read_text())
    assert result['nonce']==nonce and result['result']=='passed',result
    snapshot=json.loads((directory/result['snapshot']).read_text())
    assert snapshot['nonce']==nonce,'flush snapshot nonce mismatch'
    assert ack.stat().st_uid==uid,'acknowledgement has wrong owner'
    return dict(result,uid=uid,gid=gid,deadline_seconds=timeout)


def sample(flush=False):
    candidates=[]
    for p in Path('/proc').glob('[0-9]*'):
        try:
            if (p/'exe').readlink()!=Path('/usr/bin/ustreamer'):
                continue
            env=dict(item.split(b'=',1) for item in (p/'environ').read_bytes().split(b'\0') if b'=' in item)
            directory=Path(env[b'USTREAMER_TAILDIAG_DIR'].decode())
            status=dict(line.split(':',1) for line in (p/'status').read_text().splitlines() if ':' in line)
            uids=list(map(int,status['Uid'].split())); gids=list(map(int,status['Gid'].split()))
            assert len(set(uids))==1 and len(set(gids))==1, 'unstable process credentials'
            acknowledgement=None
            if flush:
                acknowledgement=request_flush(directory,uids[0],gids[0])
            session=json.loads((directory/'session.json').read_text())
            assert session['pid']==int(p.name)
            fields=(p/'stat').read_text().rsplit(')',1)[1].split()
            candidates.append({'pid':int(p.name),'ppid':int(fields[1]),
                'uid':uids[0],'gid':gids[0],'flush_acknowledgement':acknowledgement,
                'clock_ticks':os.sysconf('SC_CLK_TCK'),'start_ticks':int(fields[19]),'ticks':int(fields[11])+int(fields[12]),
                'rss_bytes':int(fields[21])*4096,'diagnostic_directory':str(directory),
                'session':session,'cmdline':(p/'cmdline').read_bytes().replace(b'\0',b' ').decode(),
                'executable_sha256':hashlib.file_digest((p/'exe').open('rb'),'sha256').hexdigest(),
                'diagnostic_files':{f.name:f.stat().st_size for f in directory.iterdir()}})
        except (FileNotFoundError,ProcessLookupError):
            continue
    assert len(candidates)==1,candidates
    def cmd(*args):
        p=subprocess.run(args,capture_output=True,text=True,timeout=15)
        return {'rc':p.returncode,'stdout':p.stdout,'stderr':p.stderr}
    return {'time':time.time(),'monotonic':time.monotonic(),'flush_requested':flush,
        'boot_id':Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
        'ustreamer':candidates[0],
        'video_mode':cmd('v4l2-ctl','-d','/dev/kvmd-video','--get-fmt-video','--get-parm'),
        'failed_units':cmd('systemctl','--failed','--no-legend','--plain'),
        'dmesg':cmd('dmesg'),
        'udc':{p.name:(p/'state').read_text().strip() for p in Path('/sys/class/udc').iterdir()}}


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--flush',action='store_true')
    print(json.dumps(sample(parser.parse_args().flush)))
