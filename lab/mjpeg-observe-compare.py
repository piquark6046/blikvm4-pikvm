#!/usr/bin/env python3
"""Replay M8-F0 evidence. Reports observations, never qualification acceptance."""
import argparse
import json
from pathlib import Path


def replay(root):
    clients = {}
    keyed = {}
    for name in ('direct', 'https'):
        records = []
        keys = {}
        with (root/name/'frames.jsonl').open() as f:
            for line in f:
                row = json.loads(line)
                records.append((row['monotonic'],row['sha256']))
                h = row['headers']
                key = (h.get('x-ustreamer-grab-begin-time'),h.get('x-ustreamer-encode-end-time'))
                if None in key:
                    raise ValueError('capture/encode correlation headers missing')
                keys.setdefault(key, []).append({k:row[k] for k in (
                    'index','sha256','content_length','actual_length','anomaly','trailing_hex')})
        if not records:
            raise ValueError('no frames: '+name)
        first, last = records[0][0], records[-1][0]
        fps = []
        motion_failures = []
        i = 0
        for start in range(int((last-first)//120)):
            lo = first+120*start; hi = lo+120
            while i < len(records) and records[i][0] < lo: i += 1
            j = i
            while j < len(records) and records[j][0] < hi: j += 1
            fps.append((j-i)/120)
            i = j
        i = 0
        for start in range(int((last-first)//5)):
            lo = first+5*start; hi = lo+5
            while i < len(records) and records[i][0] < lo: i += 1
            j = i
            while j < len(records) and records[j][0] < hi: j += 1
            if len({h for _,h in records[i:j]}) < 2: motion_failures.append(start)
            i = j
        clients[name] = dict(frames=len(records),observed_seconds=last-first,
            fps_120s=fps, fps_gate_met=bool(fps) and min(fps)>=27,
            motion_failure_windows=motion_failures,
            max_gap=max((b[0]-a[0] for a,b in zip(records,records[1:])),default=None),
            anomalies=sum(r['anomaly'] for rows in keys.values() for r in rows))
        keyed[name] = keys
    shared = keyed['direct'].keys() & keyed['https'].keys()
    mismatches = []
    shared_anomalies = []
    for key in sorted(shared):
        direct, https = keyed['direct'][key], keyed['https'][key]
        if {r['sha256'] for r in direct} != {r['sha256'] for r in https}:
            mismatches.append(dict(capture_encode_times=key,direct=direct,https=https))
        if any(r['anomaly'] for r in direct+https):
            shared_anomalies.append(dict(capture_encode_times=key,direct=direct,https=https))
    return dict(qualification='NOT_RUN',clients=clients,shared_capture_keys=len(shared),
        payload_mismatches=mismatches,shared_anomalies=shared_anomalies,
        interpretation='No anomaly reproduced does not establish the source of run 02 trailing bytes.')


if __name__ == '__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    a.output.write_text(json.dumps(replay(a.root),indent=2)+'\n')
