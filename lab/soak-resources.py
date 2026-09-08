#!/usr/bin/env python3
"""One read-only target sample; counters retain PID start time for CPU deltas."""
import json
import os
from pathlib import Path
import subprocess
import time


def command(*args):
    p = subprocess.run(args, capture_output=True, text=True, timeout=15)
    return {'rc': p.returncode, 'stdout': p.stdout, 'stderr': p.stderr}


def sample():
    processes = []
    all_pids = list(Path('/proc').glob('[0-9]*'))
    for p in all_pids:
        try:
            comm = (p/'comm').read_text().strip()
            exe = str((p/'exe').readlink())
            if exe == '/usr/bin/ustreamer':
                comm = 'ustreamer'
            if not (comm.startswith('kvmd') or comm in ('ustreamer', 'nginx')):
                continue
            stat = (p/'stat').read_text().rsplit(')', 1)[1].split()
            processes.append({'pid': int(p.name), 'comm': comm, 'ppid': int(stat[1]),
                              'start_ticks': int(stat[19]), 'ticks': int(stat[11])+int(stat[12]),
                              'rss_bytes': int(stat[21])*os.sysconf('SC_PAGE_SIZE'),
                              'fds': len(list((p/'fd').iterdir()))})
        except (FileNotFoundError, ProcessLookupError):
            pass
    files = ('meminfo', 'loadavg', 'stat', 'net/snmp', 'net/netstat',
             'net/sockstat', 'net/tcp', 'net/udp', 'net/unix', 'sys/fs/file-nr')
    proc = {name: (Path('/proc')/name).read_text() for name in files}
    state = command('curl', '-fsS', '--max-time', '3', '--unix-socket',
                    '/run/kvmd/ustreamer/ustreamer.sock', 'http://localhost/state')
    return {'time': time.time(), 'monotonic': time.monotonic(),
            'boot_id': Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
            'hz': os.sysconf('SC_CLK_TCK'), 'processes': processes,
            'process_count': len(all_pids), 'proc': proc,
            'socket_count': sum(len(proc['net/'+n].splitlines())-1 for n in ('tcp', 'udp', 'unix')),
            'ethernet': {p.name: int(p.read_text()) for p in Path('/sys/class/net/eth0/statistics').iterdir()},
            'failed_units': command('systemctl', '--failed', '--no-legend', '--plain'),
            'video_mode': command('v4l2-ctl', '-d', '/dev/kvmd-video', '--get-fmt-video', '--get-parm'),
            'streamer': json.loads(state['stdout']) if state['rc'] == 0 else state,
            'udc': {p.name: (p/'state').read_text().strip() for p in Path('/sys/class/udc').iterdir()}}


if __name__ == '__main__':
    print(json.dumps(sample()))
