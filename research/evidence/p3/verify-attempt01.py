#!/usr/bin/env python3
"""Replay the stopped P3-A attempt; this script cannot award P3 acceptance."""
import argparse
import hashlib
import json
import re
import runpy
import tarfile
from pathlib import Path

if not __debug__:
    raise SystemExit('Assertions are evidence gates; run without -O')
p = argparse.ArgumentParser()
p.add_argument('archive', type=Path)
a = p.parse_args()
DIGEST = 'dde56c3bf3ab1d14006c601c8c8a05343c353b11c385f9b8a33755837ed5e57a'
with a.archive.open('rb') as f:
    assert hashlib.file_digest(f, 'sha256').hexdigest() == DIGEST
assess = runpy.run_path(str(Path(__file__).with_name('inventory-gates.py')))['assess']
with tarfile.open(a.archive) as t:
    def raw(name):
        return t.extractfile(name).read()
    def obj(name):
        return json.loads(raw(name))
    hashes = obj('SHA256.json')
    names = [m.name for m in t if m.isfile()]
    assert len(names) == len(set(names))
    assert set(names) == set(hashes) | {'SHA256.json'}
    for name, digest in hashes.items():
        assert hashlib.sha256(raw(name)).hexdigest() == digest, name
    identity = obj('preparation/p2-identity.json')
    before = obj('cycle/before/target.json')
    startup = obj('cycle/startup/target.json')
    preserved = obj('cycle/failure-preservation/target.json')
    summaries = {}
    for name, r in [('before', before), ('startup', startup), ('preserved', preserved)]:
        summaries[name] = assess(r, identity, name == 'before', name == 'before')
    assert before['boot_id'] != startup['boot_id'] == preserved['boot_id']
    assert before['sd_cid'] == startup['sd_cid'] == preserved['sd_cid']
    b = raw('cycle/uart/uart-001.raw')
    markers = [b'U-Boot SPL', b'BL31:', b'U-Boot 2021', b'/boot/boot.scr',
               b'Starting kernel', b'root=PARTUUID=b14b0001-01', b'systemd[1]']
    positions = [b.index(m) for m in markers]
    assert positions == sorted(positions)
    assert b'TFTP from server' not in b and b'DHCP client bound' not in b
    events = [json.loads(l) for l in raw('cycle/uart/events.jsonl').splitlines()]
    assert sum(e['event'] == 'uart_open' for e in events) == 1
    assert not any(e['event'] == 'uart_unavailable' for e in events)
    probes = [json.loads(l) for l in raw('cycle/recovery.jsonl').splitlines()]
    successes = [e for e in probes if e.get('trusted_https')]
    assert successes and successes[0]['ssh_exit'] == 0
    assert successes[0]['boot_id'] == startup['boot_id']
    controller = obj('cycle/result.json')
    latency = (successes[0]['monotonic_ns'] - controller['reboot_request_monotonic_ns']) / 1e9
    assert 0 <= latency < 180
    assert controller['result'] == 'failed'
    browser = obj('smoke/browser-msd/result.json')
    assert browser['result'] == 'failed' and 'EACCES' in browser['browser']['error']
    assert browser['stages'] == [{'name': 'normal-login', 'connected': True, 'result': 'passed'}]
    assert t.getmember('smoke/browser-msd/001.ok').mode & 0o777 == 0o600
    assert t.getmember('smoke/browser-msd/001.ok').uid == 0
    assert obj('smoke/browser-msd/001.ok')['result'] == 'passed'
    # Review full application messages, including nginx errors logged at priority 6.
    journal = [json.loads(l) for l in preserved['commands']['journal_json']['stdout'].splitlines()]
    app_errors = []
    for event in journal:
        message = str(event.get('MESSAGE', ''))
        if re.search(r'\bERROR\b|\bCRITICAL\b|Traceback|\[error\]|\[crit\]|segfault|EXT4-fs error|I/O error', message):
            app_errors.append(event)
    assert len(app_errors) == 6
    for event in app_errors:
        message = str(event['MESSAGE'])
        assert 9_000_000 <= int(event['__MONOTONIC_TIMESTAMP']) < 12_000_000
        assert ('connect() to unix:/run/kvmd/api/kvmd.sock failed (2: No such file or directory)' in message
                or 'auth request unexpected status: 502' in message)
    assert any('Started streamer pid=' in str(e.get('MESSAGE', ''))
               and int(e['__MONOTONIC_TIMESTAMP']) > 12_000_000 for e in journal)

print(json.dumps({
    'phase': 'P3-A attempt 01', 'result': 'FAILED', 'p3_accepted': False,
    'failed_cycle': 1, 'completed_passing_cycles': 0, 'accepted_cycles': 0,
    'required_cycles': 12, 'cycle1_reboot_startup': 'PASSED',
    'cycle1_browser_smoke': 'FAILED_BEFORE_CYCLE_ACCEPTANCE',
    'failure_class': 'bridge harness permissions',
    'failure': 'root-owned 0600 browser acknowledgment unreadable by Chromium user',
    'archive_sha256': DIGEST, 'verified_members': len(hashes),
    'firmware_trace': 'complete', 'automatic_trusted_https_and_ssh_recovery_seconds': latency,
    'artifacts_and_enrollment_matched': 10690,
    'machine_and_ssh_identity_retained': True, 'physical_rw_root_retained': True,
    'postboot_failed_units': [], 'journal_records_reviewed': len(journal),
    'classified_nginx_early_startup_messages': len(app_errors),
    'uart_classification': ['two shutdown endpoint -108 messages before SPL',
                            'inherited vendor TF-A RSB address error; boot continued'],
    'core_smoke': 'incomplete; no cycle credit',
    'power_cuts_performed': 0, 'second_card_written': False,
    'sequence_stopped': True, 'target_repair_performed': False,
}, indent=2))
