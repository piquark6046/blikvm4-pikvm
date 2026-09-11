#!/usr/bin/env python3
"""Offline M8-F2 two-hour retention replay. Zero full-soak qualification credit.

Produces evidence checks and resource trends for independent review. It does
not silently turn unexplained journal events or growth into accepted results.
"""
import argparse
import collections
import json
from pathlib import Path
import re
import statistics

IMAGE = '14845cb5d5d773bc3b7411d2e939b948abc9a7fcc04229159f32a355777ec45b'


def rows(path):
    with path.open() as f:
        for line in f:
            yield json.loads(line)


def intersects(start, end, windows):
    return any(start < w['until'] and end > w['start'] for w in windows)


def duration_gate(result):
    return (result['qualification'] is False and result['diagnostic'] == 'M8-F2' and result['required_seconds'] == 7200
            and result['result'] == 'completed_pending_independent_review'
            and result['end_monotonic']-result['start_monotonic'] >= 7200)


def trend(values):
    n = len(values)
    assert n >= 2
    width = min(15, max(1, n//4))
    beginning = statistics.median(values[:width]); final = statistics.median(values[-width:])
    return {'samples': n, 'first_median': beginning, 'last_median': final,
            'delta': final-beginning, 'min': min(values), 'max': max(values),
            'monotonic_nondecreasing': all(b >= a for a, b in zip(values, values[1:])) and final > beginning}


def audit(root):
    r = json.loads((root/'result.json').read_text())
    report = {'result': 'failed', 'atx': 'DEFERRED', 'checks': {}, 'review_required': []}
    checks = report['checks']
    checks['two_hours_retention_only'] = duration_gate(r)
    start = r['start_monotonic']; end = r.get('end_monotonic', start)
    windows = list(rows(root/'lifecycle-windows.jsonl'))
    checks['bounded_lifecycle_windows'] = all(0 < w['until']-w['start'] <= 60.1 for w in windows)
    checks['no_lifecycle_exclusions'] = not r['events'] and not windows
    checks['event_actions_bounded'] = all(e['action_end'] < e['until'] for e in r['events'])
    checks['video_worker'] = json.loads((root/'video-result.json').read_text())['result'] == 'completed_pending_replay'
    checks['browser_worker'] = json.loads((root/'ui/browser-result.json').read_text())['result'] == 'completed_pending_replay'
    buckets = collections.defaultdict(lambda: {'frames': 0, 'hashes': set()})
    recovery_starts = [t for t in [start]+[w['until'] for w in windows]
                       if start <= t and t+120 <= end and not intersects(t, t+120, windows)]
    recovery_counts = [0]*len(recovery_starts)
    throughput = collections.Counter(); last = start; bad_gaps = []
    for f in rows(root/'frames.jsonl'):
        t = f['t']
        if not start <= t <= end:
            continue
        if t-last > 3 and not intersects(last, t, windows):
            bad_gaps.append([last, t])
        last = t
        bucket = buckets[int((t-start)//5)]
        bucket['frames'] += 1
        if len(bucket['hashes']) < 2:
            bucket['hashes'].add(f['sha256'])
        throughput[int((t-start)//120)] += 1
        for i, origin in enumerate(recovery_starts):
            if origin <= t < origin+120:
                recovery_counts[i] += 1
    if end-last > 3 and not intersects(last, end, windows):
        bad_gaps.append([last, end])
    checks['video_continuity'] = not bad_gaps
    report['video_gaps'] = bad_gaps
    motion_failures = []
    for i in range(int((end-start)//5)):
        if not intersects(start+i*5, start+(i+1)*5, windows) and len(buckets[i]['hashes']) < 2:
            motion_failures.append(i)
    checks['moving_video'] = not motion_failures; report['frozen_windows'] = motion_failures
    rates = []
    for i in range(int((end-start)//120)):
        if not intersects(start+i*120, start+(i+1)*120, windows):
            rates.append(throughput[i]/120)
    recovery_rates = [n/120 for n in recovery_counts]
    checks['sustained_27fps'] = bool(rates+recovery_rates) and min(rates+recovery_rates) >= 27
    report['120_second_fps'] = rates
    report['recovery_120_second_fps'] = list(zip(recovery_starts, recovery_rates))
    browser = list(rows(root/'ui/browser-samples.jsonl'))
    good = [b for b in browser if 'sha256' in b and start <= b['t'] <= end]
    stamps = [start]+[b['t'] for b in good]+[end]
    checks['actual_ui_continuity'] = bool(good) and all(b-a <= 5 or intersects(a, b, windows) for a, b in zip(stamps, stamps[1:]))
    checks['ui_auth_dimensions'] = bool(good) and all(b['api_status'] == 200 and b['width'] == 1920 and b['height'] == 1080 and b['connected'] for b in good)
    ui_windows = collections.defaultdict(set)
    for b in good:
        ui_windows[int((b['t']-start)//5)].add(b['sha256'])
    checks['actual_ui_motion'] = all(len(ui_windows[i]) >= 2 for i in range(int((end-start)//5))
                                     if not intersects(start+i*5, start+(i+1)*5, windows))
    errors = [b for b in browser if ('error' in b or 'pageerror' in b) and not intersects(b['t'], b['t']+.001, windows)]
    checks['no_unexpected_ui_errors'] = not errors
    reads = list(rows(root/'reads.jsonl'))
    checks['msd_bytes'] = bool(reads) and all(v['sha256'] == IMAGE and v['bytes'] == 8388608 for v in reads)
    target_states = [json.loads(p.read_text()) for p in (root/'msd').glob('*-target.stdout')]
    checks['real_lun_read_only'] = bool(target_states) and all(
        s['hash'] == s['legacy_hash'] == IMAGE and s['boot_id'] == r['boot_id']
        and s['lun']['ro'] == '1' and s['lun']['cdrom'] == '0'
        and s['lun']['removable'] == '0' and s['lun']['nofua'] == '0'
        and s['lun']['file'] in ('', '/usr/share/kvmd-msd/images/g4-storage.img')
        for s in target_states)
    cycles = r['cycles']
    checks['periodic_exercises'] = bool(cycles) and max([cycles[0]['start']-start, end-cycles[-1]['end']]+[b['start']-a['start'] for a,b in zip(cycles,cycles[1:])]) <= 450
    checks['host_evdev'] = bool(cycles)
    for cycle in cycles:
        folder = root/f"cycle-{cycle['index']:04d}-hid"
        hid = json.loads((folder/'result.json').read_text())
        checks['host_evdev'] &= hid['result'] == 'passed' and len(hid['checks']) == 6
        for label in hid['checks']:
            evidence = json.loads((folder/(label+'.json')).read_text())
            checks['host_evdev'] &= evidence['actual'] == evidence['expected']
            # Replay the decoder independently from archived actual/expected equality.
            for events, actual in zip(evidence['events'], evidence['actual']):
                frames = []; frame = []
                for ev in events:
                    triple = [ev['type'], ev['code'], ev['value']]
                    if triple == [0, 0, 0]: frames.append(frame); frame = []
                    elif triple[:2] != [4, 4]: frame.append(triple)
                checks['host_evdev'] &= not frame and frames == actual
    samples = list(rows(root/'resources.jsonl'))
    stamps = [start]+[s['bridge_monotonic'] for s in samples]+[end]
    checks['resource_coverage'] = len(samples) >= 120 and all(b-a <= 120 for a,b in zip(stamps, stamps[1:]))
    checks['same_boot'] = all(s['boot_id'] == r['boot_id'] for s in samples)
    checks['uart_monitor'] = not r['uart_errors'] and (root/'uart.log').exists() and (root/'uart-monitor.json').exists()
    checks['systemd'] = all(s['failed_units']['rc'] == 0 and not s['failed_units']['stdout'].strip() for s in samples)
    steady = [s for s in samples if not s['planned']]
    checks['exact_mode'] = bool(steady) and all(s['video_mode']['rc'] == 0 and all(v in s['video_mode']['stdout'] for v in ('1920/1080', "'MJPG'", '30.000 (30/1)')) for s in steady)
    checks['one_streamer'] = all(len([p for p in s['processes'] if p['comm'] == 'ustreamer']) == 1 for s in steady)
    checks['streamer_parent'] = all(any(p['comm'].startswith('kvmd') and p['pid'] == u['ppid'] for p in s['processes'])
                                     for s in steady for u in s['processes'] if u['comm'] == 'ustreamer')
    checks['udc_configured'] = all(list(s['udc'].values()) == ['configured'] for s in steady)
    checks['two_clients'] = all(s['streamer']['result']['stream']['clients'] == 2 for s in steady)
    groups = collections.defaultdict(list)
    for s in steady:
        for proc in s['processes']:
            groups[(proc['comm'], proc['pid'], proc['start_ticks'])].append((s['monotonic'], proc, s['hz']))
    report['process_trends'] = {}
    for key, group in groups.items():
        if len(group) < 2: continue
        name = ':'.join(map(str, key)); first, last = group[0], group[-1]
        report['process_trends'][name] = {field: trend([g[1][field] for g in group]) for field in ('rss_bytes', 'fds')}
        report['process_trends'][name]['cpu_one_core_percent'] = (last[1]['ticks']-first[1]['ticks'])/first[2]/(last[0]-first[0])*100
    report['system_trends'] = {key: trend([s[key] for s in steady]) for key in ('process_count', 'socket_count')}
    report['first_last_memory'] = {'baseline': steady[0]['proc']['meminfo'], 'final': steady[-1]['proc']['meminfo']}
    report['ethernet_delta'] = {key: steady[-1]['ethernet'][key]-steady[0]['ethernet'][key] for key in steady[0]['ethernet']}
    report['review_required'].append('Review all process generations and system trends for unexplained growth; service restarts must not conceal within-generation leaks.')
    findings = {}
    for name in ('host-kernel-live.log', 'target-journal-live.log'):
        findings[name] = [line for line in (root/name).read_text().splitlines() if re.search(r'error|fail|timeout|timed out|reset|stall|BUG:|Oops|traceback|out of memory', line, re.I)]
    report['journal_candidates'] = findings
    report['review_required'].append('Audit full host/target journals and map every candidate to bounded planned actions or a documented benign cause; retain unexplained failures.')
    report['qualification_seconds'] = 0
    report['result'] = 'evidence_gates_passed_review_pending' if all(checks.values()) else 'failed'
    return report


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--root', type=Path, required=True); p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    try:
        result = audit(a.root)
    except Exception as ex:
        result = {'result': 'failed', 'error': str(ex)}
    a.output.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({'result': result['result'], 'checks': result.get('checks'), 'error': result.get('error')}))
    raise SystemExit(result['result'] == 'failed')
