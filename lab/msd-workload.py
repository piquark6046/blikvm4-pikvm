#!/usr/bin/env python3
"""Continuous direct whole-image reads during each accepted HID/video workload."""
import argparse
import hashlib
import json
import mmap
import os
import re
from pathlib import Path
import runpy
import subprocess
import sys
import threading
import time

M=runpy.run_path(str(Path(__file__).with_name('msd-hil.py')))
p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--boot-result',type=Path,required=True);p.add_argument('--browser',action='store_true');a=p.parse_args()
h=M['Harness'](a.output,a.boot_result)
result={'result':'failed','direct_reads':0};stop=threading.Event();errors=[];thread=None;work=None
monitor=M['H']['G1']['HostMonitor'](h.rec)
def reader():
    try:
        fd=os.open(h.identity['node'],os.O_RDONLY|os.O_DIRECT)
        with mmap.mmap(-1,8388608) as buffer,(a.output/'reads.jsonl').open('w') as log:
            try:
                while not stop.is_set():
                    start=time.time();os.lseek(fd,0,os.SEEK_SET)
                    n=os.readv(fd,[buffer]);assert n==8388608,n
                    digest=hashlib.sha256(buffer).hexdigest();assert digest==M['IMAGE_HASH'],digest
                    log.write(json.dumps({'start':start,'end':time.time(),'bytes':n,'sha256':digest})+'\n');log.flush()
                    result['direct_reads']+=1
            finally:os.close(fd)
    except Exception as ex:errors.append(str(ex));stop.set()
try:
    h.state('workload-before',True);h.ready('workload-before');monitor.start()
    thread=threading.Thread(target=reader);thread.start()
    script='lab/hid-browser-hil.py' if a.browser else 'lab/hid-workload.py'
    argv=[sys.executable,script,'--output',str(a.output/'hid-video'),'--boot-result',str(a.boot_result)]
    if a.browser:argv.append('--workload')
    start=time.monotonic()
    with (a.output/'workload.log').open('w') as log:
        work=subprocess.Popen(argv,stdout=log,stderr=log)
        while work.poll() is None:
            assert not errors,errors
            assert time.monotonic()-start<700,'workload timeout'
            time.sleep(.2)
    result['hid_video']=json.loads((a.output/'hid-video/result.json').read_text())
    assert work.returncode==0,result['hid_video']
    assert not errors and result['direct_reads']>=20,(errors,result['direct_reads'])
    stop.set();thread.join(timeout=15);assert not thread.is_alive()
    h.client.login();h.state('workload-after',True);h.media('workload-after')
    result['elapsed']=time.monotonic()-start;result['result']='passed'
except Exception as ex:result['error']=str(ex)
finally:
    stop.set()
    if work and work.poll() is None:work.terminate();work.wait(timeout=15)
    if thread:thread.join(timeout=15)
    monitor.stop()
    log=(a.output/'host-kernel-live.log').read_text() if (a.output/'host-kernel-live.log').exists() else ''
    bad=[line for line in log.splitlines() if re.search(r'reset (?:high|full|SuperSpeed)|timed out|timeout|DID_TIME_OUT|host reset|device reset',line,re.I)]
    result['host_transport_errors']=bad
    if bad:result.update(result='failed',error='host transport errors')
    result['transitions']=h.result['transitions'];h.rec.save_text('result.json',json.dumps(result,indent=2)+'\n')
raise SystemExit(result['result']!='passed')
