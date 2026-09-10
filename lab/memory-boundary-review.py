#!/usr/bin/env python3
"""Offline, hash-pinned Run 03 restart boundary review; never modifies input."""
import hashlib
import json
from pathlib import Path
import statistics

ROOT = Path('out/m8f0/soak03-review/original')
OUT = Path('research/evidence/m8f1/run03-boundary.json')

def main():
    sources = {}
    for name, expected in [('resources.jsonl', 'e52a76d0676e9bf77044e4c113f03919c292cb66e54d1b049ca2e3d693c8ad45'), ('result.json', '3f2d8b6b20fde939f186e8dae13c510a946fff37c2f848dbf5b1f6b5feda28ab')]:
        sources[name] = hashlib.sha256((ROOT/name).read_bytes()).hexdigest()
        assert sources[name] == expected
    samples = [json.loads(line) for line in (ROOT/'resources.jsonl').read_text().splitlines()]
    event = next(e for e in json.loads((ROOT/'result.json').read_text())['events'] if e['event'] == 'kvmd')
    t = event['start']
    stable = next(s['bridge_monotonic'] for s in samples if s['bridge_monotonic'] >= event['until'] and s['streamer'].get('result', {}).get('stream', {}).get('clients') == 2 and any(p['comm'].startswith('kvmd/main') for p in s['processes']))
    def metrics(s):
        d = {k: s[k] for k in ('process_count', 'socket_count')}
        for line in s['proc']['meminfo'].splitlines():
            k, v = line.split(':', 1)
            if k in ('MemAvailable', 'MemFree', 'Cached', 'Slab', 'SReclaimable', 'SUnreclaim', 'Shmem', 'PageTables', 'KernelStack', 'AnonPages'):
                d[k+'_bytes'] = int(v.split()[0])*1024
        for k, v in zip(('allocated', 'unused', 'limit'), s['proc']['sys/fs/file-nr'].split()):
            d['file_nr_'+k] = int(v)
        for p in s['processes']:
            d[f"rss_bytes:{p['comm']}:{p['pid']}:{p['start_ticks']}"] = p['rss_bytes']
            if p['comm'].startswith('kvmd/main'):
                d['kvmd_main_rss_bytes'] = p['rss_bytes']
            if p['comm'] == 'ustreamer':
                d['ustreamer_rss_bytes'] = p['rss_bytes']
        return d
    windows = {}
    for name, a, b in [('pre30', t-1800, t), ('pre5', t-300, t), ('stable_post5', stable, stable+300), ('post30', event['action_end'], event['action_end']+1800)]:
        selected = [s for s in samples if a <= s['bridge_monotonic'] < b]
        values = [metrics(s) for s in selected]
        keys = sorted(set().union(*(v.keys() for v in values)))
        windows[name] = {'start': a, 'end_exclusive': b, 'samples': len(selected), 'medians': {k: statistics.median(v[k] for v in values if k in v) for k in keys}, 'metric_samples': {k: sum(k in v for v in values) for k in keys}}
    before = windows['pre5']['medians']; after = windows['stable_post5']['medians']
    delta = {k: after[k]-before[k] for k in sorted(before.keys() & after.keys())}
    immediate = [s for s in samples if t-120 <= s['bridge_monotonic'] <= stable+120]
    result = {'schema': 1, 'diagnostic': 'M8-F1 Stage 0', 'sources_sha256': sources, 'event': event, 'stable_definition': 'First sample after original recovery deadline with two clients and main kvmd present; not proof of allocator equilibrium.', 'windows': windows, 'post5_minus_pre5': delta, 'boundary_samples': [{'bridge_monotonic': s['bridge_monotonic'], 'metrics': metrics(s)} for s in immediate], 'limitations': ['Minute sampling cannot measure instantaneous release or separate old-process exit from new-process allocation.', 'No anonymous/private/PSS or filesystem allocation evidence; shared RSS cannot be summed as physical memory.', 'Restart replaces kvmd children and uStreamer too; system recovery is not attributable solely to kvmd main.'], 'decision': 'Memory attribution remains inconclusive; targeted live run required', 'm8f': 'OPEN', 'run03_failed': False, 'p1': 'GATED'}
    OUT.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(delta, indent=2))

if __name__ == '__main__':
    main()
