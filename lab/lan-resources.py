#!/usr/bin/env python3
"""Target read-only per-process, CPU, Ethernet and streamer sampling."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time

stop=time.monotonic()+float(sys.argv[1])
while time.monotonic()<stop:
    processes=[]
    for p in Path('/proc').glob('[0-9]*'):
        try:
            comm=(p/'comm').read_text().strip()
            if (p/'exe').readlink() == Path('/usr/bin/ustreamer'): comm='ustreamer'
            if not (comm.startswith('kvmd') or comm in ('ustreamer','nginx')): continue
            stat=(p/'stat').read_text().rsplit(')',1)[1].split()
            processes.append({'pid':int(p.name),'comm':comm,'ppid':int(stat[1]),
                              'ticks':int(stat[11])+int(stat[12]),'rss_bytes':int(stat[21])*os.sysconf('SC_PAGE_SIZE'),
                              'cmdline':(p/'cmdline').read_bytes().replace(b'\0',b' ').decode()})
        except (FileNotFoundError,ProcessLookupError):pass
    counters={f.name:int(f.read_text()) for f in Path('/sys/class/net/eth0/statistics').iterdir()}
    state=subprocess.run(['curl','-sS','--max-time','1','--unix-socket','/run/kvmd/ustreamer/ustreamer.sock','http://localhost/state'],capture_output=True,text=True)
    print(json.dumps({'time':time.time(),'monotonic':time.monotonic(),'hz':os.sysconf('SC_CLK_TCK'),
                      'cpu':list(map(int,Path('/proc/stat').read_text().splitlines()[0].split()[1:])),
                      'processes':processes,'ethernet':counters,'snmp':Path('/proc/net/snmp').read_text(),'streamer':json.loads(state.stdout) if state.returncode==0 else {'error':state.stderr}}),flush=True)
    time.sleep(2)
