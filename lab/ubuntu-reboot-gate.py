#!/usr/bin/env python3
"""Audit an uninterrupted M7 reboot series against archived UART and unit evidence."""
import argparse
import hashlib
import json
from pathlib import Path
import re

UUID = r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}'


def audit(series, runs, count):
    reports = [json.loads(line) for line in series.read_text().splitlines() if line.strip()]
    if len(reports) != count or len({r['run_id'] for r in reports}) != count:
        raise ValueError('wrong number of distinct runs')
    output = []
    expected_artifacts = None
    previous_boot = None
    previous_finish = None
    for report in reports:
        path = runs / report['run_id']
        saved = json.loads((path / 'test-results.json').read_text())
        meta = json.loads((path / 'metadata.json').read_text())
        if saved != report or report['result'] != 'passed' or report['stage'] != 'ubuntu_network_ssh':
            raise ValueError('run did not pass M7-B/C')
        if expected_artifacts is None:
            expected_artifacts = meta['artifacts']
        if meta['artifacts'] != expected_artifacts or meta['target_storage_writes']:
            raise ValueError('artifact drift or target storage write')
        if previous_finish and meta['started_at'] < previous_finish:
            raise ValueError('runs are not sequential')
        previous_finish = report['finished_at']
        identity = (path / 'identity.log').read_text()
        ids = re.findall('^' + UUID + '$', identity, re.M)
        if len(ids) != 1 or ids[0] in [r['boot_id'] for r in output]:
            raise ValueError('missing or repeated boot identity')
        raw = (path / 'uart.raw').read_text(errors='replace')
        shutdown, separator, _ = raw.partition('U-Boot SPL 2021.10-armbian')
        if not separator or not all(s in shutdown for s in ('systemctl reboot', 'reboot.target', 'reboot: Restarting system')):
            raise ValueError('clean systemd shutdown before vendor U-Boot is unproven')
        if previous_boot and 'bootid=' + previous_boot not in shutdown:
            raise ValueError('reboot chain is interrupted')
        previous_boot = ids[0]
        for name in ('pid1.log', 'multi-user.log', 'systemctl-failed.log', 'systemctl-status.log',
                     'journal.log', 'ip-addr.log', 'ip-route.log', 'ethtool.log', 'ping.log',
                     'sshd-effective.log', 'ssh-authentication.log', 'lab-service-policy.log',
                     'dmesg.log', 'uboot.log', 'runner.py', 'rootfs-manifest.json'):
            if not (path / name).is_file():
                raise ValueError('missing evidence: ' + name)
        if (path / 'pid1.log').read_text().strip() != 'systemd':
            raise ValueError('PID 1 is not systemd')
        if (path / 'multi-user.log').read_text().split() != ['active', 'active']:
            raise ValueError('multi-user or serial getty inactive')
        if not re.search(r'^\s*State: running\s*$', (path / 'systemctl-status.log').read_text(), re.M):
            raise ValueError('systemd was not settled in running state')
        if (path / 'systemd-ready.log').exists() and (path / 'systemd-ready.log').read_text().strip() != 'running':
            raise ValueError('systemd readiness check did not pass')
        if '0 loaded units listed.' not in (path / 'systemctl-failed.log').read_text():
            raise ValueError('failed-unit report is not empty')
        ssh = (path / 'sshd-effective.log').read_text().splitlines()
        if not all(s in ssh for s in ('passwordauthentication no', 'kbdinteractiveauthentication no',
                                      'permitrootlogin no', 'authenticationmethods publickey')):
            raise ValueError('SSH policy mismatch')
        output.append({'run_id': report['run_id'], 'boot_id': ids[0],
                       'started_at': meta['started_at'], 'finished_at': report['finished_at'],
                       'uart_sha256': hashlib.sha256((path / 'uart.raw').read_bytes()).hexdigest()})
    # Reject an omitted intervening boot attempt, including failed attempts.
    candidates = []
    for path in runs.iterdir():
        if (path / 'metadata.json').is_file():
            meta = json.loads((path / 'metadata.json').read_text())
            if meta['command'] == 'boot-ubuntu' and output[0]['started_at'] <= meta['started_at'] <= output[-1]['started_at']:
                candidates.append(meta['run_id'])
    if set(candidates) != {r['run_id'] for r in output}:
        raise ValueError('an intervening boot attempt was omitted')
    return {'result': 'passed', 'consecutive_clean_boots': count,
            'final_20_boot_gate': count == 20, 'artifacts': expected_artifacts, 'runs': output}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--series', type=Path, required=True)
    parser.add_argument('--runs', type=Path, required=True)
    parser.add_argument('--count', type=int, choices=(2, 5, 20), required=True)
    args = parser.parse_args()
    print(json.dumps(audit(args.series, args.runs, args.count), indent=2))
