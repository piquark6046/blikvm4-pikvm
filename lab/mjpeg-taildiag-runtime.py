#!/usr/bin/env python3
"""Read-only diagnostic identity sample; --flush requests only a ring snapshot."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import time


def sample(flush=False):
    candidates=[]
    for p in Path('/proc').glob('[0-9]*'):
        try:
            if (p/'exe').readlink()!=Path('/usr/bin/ustreamer'):
                continue
            env=dict(item.split(b'=',1) for item in (p/'environ').read_bytes().split(b'\0') if b'=' in item)
            directory=Path(env[b'USTREAMER_TAILDIAG_DIR'].decode())
            if flush:
                # This must precede every slower runtime command.
                (directory/'flush.request').touch(mode=0o600,exist_ok=True)
            session=json.loads((directory/'session.json').read_text())
            assert session['pid']==int(p.name)
            fields=(p/'stat').read_text().rsplit(')',1)[1].split()
            candidates.append({'pid':int(p.name),'ppid':int(fields[1]),
                'start_ticks':int(fields[19]),'ticks':int(fields[11])+int(fields[12]),
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
