"""Fail-closed P3 snapshot checks. Raw logs remain available for full review."""
import json
import re

WARNINGS = [
    r'Static allocation of GPIO base|using dummy regulator|dummy supplies not allowed',
    r'local system does not support BPF/cgroup firewalling|first unit using IP firewalling',
    r"Couldn't write .* to '(kernel/core_pattern|net/ipv6/conf/(all|default)/use_tempaddr|kernel/yama/ptrace_scope)'",
    r'Not using persistent file timestamp .* as it is in the future',
    r'Found matching .network file, based on potentially unpredictable interface name',
    r'Binding to IPv6 address not available since kernel does not support IPv6',
]
OFFLINE_WARNINGS = [r'Timeout occurred while waiting for network connectivity',
    r'systemd-networkd-wait-online.service: Failed with result',
    r'Failed to start systemd-networkd-wait-online.service']

def assess(r, identity, offline=False, accepted_p2_boot=False):
    c = r['commands']
    assert all(x.get('returncode') == 0 for x in c.values()), 'inventory command failed'
    root = json.loads(c['root']['stdout'])['filesystems'][0]
    assert root['source'] == '/dev/mmcblk0p1' and root['fstype'] == 'ext4'
    assert 'rw' in root['options'].split(',')
    assert c['blkid']['stdout'] == identity['blkid'], 'root identity changed'
    assert r['machine_id'] == identity['machine_id'], 'machine identity changed'
    assert r['host_public_keys'] == identity['host_public_keys'], 'SSH identity changed'
    assert len(r['hash_checks']) == 10690
    assert all(v['matches'] and v['sha256'] == v['expected'] for v in r['hash_checks'].values()), 'production artifact changed'
    cmd = c['cmdline']['stdout']
    assert 'root=PARTUUID=b14b0001-01' in cmd and not re.search(r'root=/dev/ram|nfsroot=|ip=dhcp', cmd)
    assert '1920/1080' in c['v4l2']['stdout'] and "'MJPG'" in c['v4l2']['stdout']
    assert '30.000 (30/1)' in c['v4l2']['stdout']
    failed = [l.split()[0] for l in c['failed_units']['stdout'].splitlines()]
    assert failed == (['systemd-networkd-wait-online.service'] if offline else []), failed
    show = dict(l.split('=', 1) for l in c['ssh_show']['stdout'].splitlines() if '=' in l)
    assert show['ActiveState'] == 'active' and show['NRestarts'] == '0'
    assert show['RestartPreventExitStatus'] == '255'
    units = [dict(l.split('=', 1) for l in part.splitlines() if '=' in l)
             for part in c['services']['stdout'].strip().split('\n\n')]
    assert len(units) == 4 and all(u['ActiveState'] == 'active' for u in units)
    assert {u['Id'] for u in units} == {'kvmd.service', 'nginx.service', 'blikvm-gadget.service', 'blikvm-msd-helper.service'}
    assert {l.split()[4] for l in c['listeners']['stdout'].splitlines()[1:] if l.startswith('tcp')} == {'192.168.88.2:22','192.168.88.2:443'}
    assert 'default ' not in c['routes']['stdout']
    cfg = dict(l.split('=',1) for l in c['journald_config']['stdout'].splitlines() if l and not l.startswith('#') and '=' in l)
    assert cfg['Storage'] == 'volatile' and cfg['RuntimeMaxUse'] == '16M' and cfg['RuntimeMaxFileSize'] == '4M'
    assert int(c['journal_allocation']['stdout'].split()[0]) <= 16384
    patterns = WARNINGS + (OFFLINE_WARNINGS if offline else [])
    unclassified = [l for l in c['high_severity']['stdout'].splitlines() if l.strip() and not any(re.search(p,l) for p in patterns)]
    assert not unclassified, 'unclassified warning/high severity: ' + repr(unclassified)
    # Journald priority can miss application errors; scan full journal and dmesg too.
    bad = [l for l in (c['journal']['stdout'] + c['dmesg']['stdout']).splitlines()
           if re.search(r'ERROR|CRITICAL|Traceback|segfault|EXT4-fs error|I/O error|Buffer I/O|Kernel panic|Oops:|checksum error|DID_TIME_OUT|reset high-speed USB', l)]
    if accepted_p2_boot:
        assert r['boot_id'] == identity['boot_id']
        bad = [l for l in bad if not ('invalid-m8d' in l and 'Got access denied for user' in l)]
    assert not bad, 'unexpected full-log error: ' + repr(bad)
    return {'result':'passed', 'artifacts_matched':len(r['hash_checks']), 'boot_id':r['boot_id'], 'warning_lines_classified':len(c['high_severity']['stdout'].splitlines())}
