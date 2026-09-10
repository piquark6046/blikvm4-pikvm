#!/usr/bin/env python3
"""Read-only M8-F1 sample, stdout only; no fd names or process arguments."""
import json
import os
from pathlib import Path
import runpy
import subprocess
import time


def sample(base):
    start = time.monotonic()
    row = base()
    for p in row['processes']:
        root = Path('/proc')/str(p['pid'])
        try:
            raw = {}
            for name in ('status', 'smaps_rollup', 'stat'):
                try:
                    raw[name] = (root/name).read_text()
                except FileNotFoundError:
                    if name != 'smaps_rollup':
                        raise
                    raw[name] = None
                    p.setdefault('unavailable', []).append(name)
            ticks = int(raw['stat'].rsplit(')', 1)[1].split()[19])
            if ticks != p['start_ticks']:
                raise RuntimeError('PID generation changed during sample')
            fields = {}
            for name in ('status', 'smaps_rollup'):
                for line in (raw[name] or '').splitlines():
                    if ':' not in line:
                        continue
                    key, value = line.split(':', 1)
                    words = value.split()
                    if len(words) == 2 and words[1] == 'kB':
                        fields[key+'_bytes'] = int(words[0])*1024
            p.update(raw=raw, memory=fields)
        except (FileNotFoundError, ProcessLookupError) as ex:
            p['sample_error'] = type(ex).__name__
    for name in ('vmstat', 'slabinfo'):
        path = Path('/proc')/name
        row['proc'][name] = path.read_text() if path.exists() else None
        if not path.exists():
            row.setdefault('unavailable', []).append('/proc/'+name)
    row['runtime_usage'] = {}
    for name in ('/run', '/dev/shm', '/var/log', '/var/lib/kvmd', '/tmp'):
        path = Path(name)
        if path.exists():
            v = os.statvfs(path)
            r = subprocess.run(['du', '-sx', '-B1', name], capture_output=True, text=True, timeout=10)
            row['runtime_usage'][name] = {'filesystem_total_bytes': v.f_blocks*v.f_frsize, 'filesystem_used_bytes': (v.f_blocks-v.f_bfree)*v.f_frsize, 'allocated_bytes': int(r.stdout.split()[0]) if r.returncode == 0 else None, 'du_rc': r.returncode}
    # Other processes, excluding this short-lived sampler; no cmdline/env/FD targets.
    row['other_processes'] = []
    selected = {p['pid'] for p in row['processes']}
    for path in Path('/proc').glob('[0-9]*'):
        if int(path.name) in selected or int(path.name) == os.getpid():
            continue
        try:
            fields = (path/'stat').read_text().rsplit(')', 1)[1].split()
            row['other_processes'].append({'pid': int(path.name), 'comm': (path/'comm').read_text().strip(), 'start_ticks': int(fields[19]), 'rss_bytes': int(fields[21])*os.sysconf('SC_PAGE_SIZE')})
        except (FileNotFoundError, ProcessLookupError):
            pass
    row['sampling_seconds'] = time.monotonic()-start
    return row

if __name__ == '__main__':
    base = runpy.run_path('/run/m8f1-soak-resources.py')['sample']
    print(json.dumps(sample(base)))
