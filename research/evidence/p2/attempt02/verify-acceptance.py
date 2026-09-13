#!/usr/bin/env python3
"""Replay P2 attempt 02 from immutable private archives; publish no raw logs."""
import argparse
import hashlib
import json
import re
import subprocess
import sys
import tarfile
from pathlib import Path

if not __debug__:
    raise SystemExit('Run without -O: assertions are qualification gates')
p = argparse.ArgumentParser()
p.add_argument('private_directory', type=Path)
a = p.parse_args()
previous = json.loads(subprocess.check_output([
    sys.executable, str(Path(__file__).with_name('verify-progress.py')),
    str(a.private_directory)], text=True))
assert previous['result'] == 'completed_gates_replayed'
archives = {
    'write-evidence.tar.gz': '051d990253e019c63c042e3050fe668d8d0d04cc23085be5a0a0809ee4902a56',
    'reinsert-evidence.tar.gz': '7e2c758e6eeb428e5916bd73207ea5837fbd4782125889eae9bf2a5fc1c9b755',
    'live-insertion-recheck.tar.gz': 'f56dcf2022881872cc3d372746570d13ed29e8e1d7424d1d848791a625a07bea',
    'coldboot01-recovery.tar.gz': '3eebf57dd64639ce821b85d8e646ad8087473d7363d4ace0fb91469771acf1f9',
    'coldboot02-recovery.tar.gz': '02b3817d554ec5beaedfc15c69ce3b383a943d8e8af4e8ceeac86cd15d7c7761',
    'final-evidence.tar.gz': '1cbc3e9d529fb23b045750219d2a1e7de57e89713fe4c553adf24993484b7b08',
}
verified = dict(previous['archives'])
def raw(archive, name):
    with tarfile.open(a.private_directory / archive) as t:
        return t.extractfile(name).read()
def obj(archive, name):
    return json.loads(raw(archive, name))
for archive, digest in archives.items():
    with (a.private_directory / archive).open('rb') as f:
        assert hashlib.file_digest(f, 'sha256').hexdigest() == digest, archive
    verified[archive] = {'sha256': digest}
for archive, prefix in [('coldboot01-recovery.tar.gz', 'recovery01-snapshot/'),
                        ('coldboot02-recovery.tar.gz', 'recovery01-snapshot/'),
                        ('final-evidence.tar.gz', '')]:
    members = obj(archive, prefix + 'SHA256.json')
    with tarfile.open(a.private_directory / archive) as t:
        for name, digest in members.items():
            assert hashlib.sha256(t.extractfile(prefix + name).read()).hexdigest() == digest, name
    verified[archive]['verified_members'] = len(members)
image = 'c261a2328594bca90f6a47bc566429a5684c0bf573de0d4089f2843f114eae24'
write = obj('write-evidence.tar.gz', 'write-result.json')
reinsert = obj('reinsert-evidence.tar.gz', 'reinsert-result.json')
for result in [write, reinsert]:
    assert result['result'] == 'passed' and result['image_sha256'] == image
    readback = result['readback']
    assert readback['every_byte_compared'] and readback['O_DIRECT']
    assert readback['bytes_read'] == 1077936128 and readback['sha256'] == image
assert all(write[k] for k in ['write_completed', 'fsync_completed', 'flush_completed'])
assert reinsert['physical_reinsert_verified']
assert write['state']['diskseq'] != reinsert['state']['diskseq']
checks = obj('reinsert-evidence.tar.gz', 'post-reinsert-checks.json')
assert checks['result'] == 'passed' and checks['fsck_exit'] == 0
assert checks['prefix_bytes_directly_compared'] == 4194304
assert len(checks['raw_bootloader_direct_read']) == 2
recheck = obj('live-insertion-recheck.tar.gz', 'result.json')
assert recheck['result'] == 'passed' and not recheck['target_or_sd_writes']
assert recheck['O_DIRECT'] and recheck['byte_identical'] and not recheck['differing_chunk_offsets']
assert recheck['sha256'] == image and recheck['bytes_read'] == 1077936128
assert recheck['fsck_exit'] == 0 and all(x['matches'] for x in recheck['bootloader'])
recoveries = []
startups = []
for archive in ['coldboot01-recovery.tar.gz', 'coldboot02-recovery.tar.gz']:
    prefix = 'recovery01-snapshot/'
    result = obj(archive, prefix + 'recovery01/result.json')
    gate = obj(archive, prefix + 'connect-authorized.json')['offline_gate']
    assert gate['offline_gate_passed'] and gate['continuous_since_systemd']
    assert gate['carrier_zero_during_boot'] and gate['offline_seconds_since_login'] >= 300
    assert result['result'] == 'passed' and not result['manual_repair']
    latency = result['first_success_latency_seconds']
    assert all(0 <= latency[k] <= 60 for k in ['icmp', 'tcp22', 'tcp443', 'https', 'ssh'])
    tls = result['first_success']['https']
    assert tls['certificate_matches_enrollment'] and tls['normal_CA_hostname_validation']
    startup = obj(archive, prefix + 'recovery01/startup-evidence.json')
    startups.append(startup)
    c = startup['commands']
    show = dict(line.split('=', 1) for line in c['ssh_show']['stdout'].splitlines() if '=' in line)
    assert show['NRestarts'] == '0' and show['RestartPreventExitStatus'] == '255'
    assert show['ActiveState'] == 'active'
    listen = re.search(r'\[\s*([\d.]+)\].*Server listening on 192.168.88.2 port 22', c['ssh_journal']['stdout'])
    carrier = re.search(r'\[\s*([\d.]+)\].*eth0: Gained carrier', c['networkd_journal']['stdout'])
    assert listen and carrier and float(listen[1]) < float(carrier[1])
    assert not re.search(r'Cannot assign requested address|status=255|Failed to start', c['ssh_journal']['stdout'])
    recoveries.append({'https_seconds': latency['https'], 'ssh_seconds': latency['ssh'],
                       'offline_dwell_seconds': gate['offline_seconds_since_login'],
                       'sshd_listen_boot_seconds': float(listen[1]),
                       'carrier_boot_seconds': float(carrier[1]), 'ssh_restarts': 0})
assert startups[0]['boot_id'] != startups[1]['boot_id']
A = 'final-evidence.tar.gz'
controller = obj(A, 'second-cold-core/controller-result.json')
assert controller['result'] == 'passed' and all(s['result'] == 'passed' for s in controller['stages'])
assert obj(A, 'second-cold-core/browser-msd/result.json')['result'] == 'passed'
assert len(obj(A, 'second-cold-core/browser-msd/result.json')['stages']) == 11
combined = obj(A, 'second-cold-core/two-client-hid-msd/result.json')
ui = obj(A, 'second-cold-core/browser-hid-msd/result.json')
assert combined['result'] == ui['result'] == 'passed'
assert combined['direct_reads'] >= 20 and ui['direct_reads'] >= 20
video = combined['hid_video']['video']
assert video['client_count'] == 2 and video['seconds'] == 120
for i, client in enumerate(video['clients']):
    assert client['capacity_passed'] and client['fps'] >= 27 and client['frames'] >= 3240 and client['max_gap'] <= 3
    frames = [json.loads(line) for line in raw(A, f'second-cold-core/two-client-hid-msd/hid-video/two-clients/client-{i}/frames.jsonl').splitlines()]
    assert len(frames) == client['frames']
    assert all(len({f['sha256'] for f in frames if w*5 <= f['t'] < (w+1)*5}) >= 2 for w in range(24))
review = obj(A, 'coldboot02/final-review.json')
assert review['result'] == 'passed' and review['all_selected_artifacts_match']
assert len(review['hash_checks']) == 10686
assert all(v['matches'] and v['sha256'] == v['expected'] for v in review['hash_checks'].values())
assert review['identity_retained'] and review['persistence_retained']
assert set(review['enrollment']) == {'etc/kvmd/htpasswd', 'etc/kvmd/nginx/ssl/server.crt', 'etc/kvmd/nginx/ssl/server.key', 'home/blikvm/.ssh/authorized_keys'}
assert all(v['matches'] for v in review['enrollment'].values())
assert review['commands']['nonlocal_bind']['stdout'].strip() == 'net.ipv4.ip_nonlocal_bind = 0'
state = obj(A, 'coldboot02/final-state.json')
assert state['boot_id'] == review['boot_id'] == startups[1]['boot_id']
c = state['commands']
show = dict(line.split('=', 1) for line in c['ssh_show']['stdout'].splitlines() if '=' in line)
assert show['NRestarts'] == '0' and show['ActiveState'] == 'active' and show['RestartPreventExitStatus'] == '255'
assert [s for s in c['sshd_T']['stdout'].splitlines() if s.startswith('listenaddress ')] == ['listenaddress 192.168.88.2:22']
assert c['socket_state']['stdout'].strip() == 'disabled' and c['socket_active']['stdout'].strip() == 'inactive'
assert {line.split()[4] for line in c['listeners']['stdout'].splitlines()[1:]} == {'192.168.88.2:22', '192.168.88.2:443'}
normalize = lambda s: re.sub(r'counter packets \d+ bytes \d+', 'counter', s)
assert normalize(c['firewall']['stdout']) == normalize(startups[0]['commands']['firewall']['stdout'])
assert c['network_config']['stdout'] == startups[0]['commands']['network_config']['stdout']
assert 'ConfigureWithoutCarrier=yes\n' in c['network_config']['stdout']
assert 'default ' not in c['routes']['stdout']
logging = dict(line.split('=', 1) for line in c['journald_config']['stdout'].splitlines() if line and not line.startswith('#') and '=' in line)
assert logging['Storage'] == 'volatile' and logging['RuntimeMaxUse'] == '16M' and logging['RuntimeMaxFileSize'] == '4M'
allocation = int(c['logging_allocation']['stdout'].splitlines()[0].split()[0])
assert allocation <= 16384
failed = [line.split()[0] for line in c['failed_units']['stdout'].splitlines() if ' loaded failed ' in line]
assert failed == ['systemd-networkd-wait-online.service']
warning_patterns = {
    'legacy_gpio_regulator': r'Static allocation of GPIO base|using dummy regulator|dummy supplies not allowed',
    'unsupported_bpf_firewall': r'local system does not support BPF/cgroup firewalling|first unit using IP firewalling',
    'unsupported_sysctl': r"Couldn't write .* to '(kernel/core_pattern|net/ipv6/conf/(all|default)/use_tempaddr|kernel/yama/ptrace_scope)'",
    'inherited_rtc': r'Not using persistent file timestamp .* as it is in the future',
    'interface_name': r'Found matching .network file, based on potentially unpredictable interface name',
    'expected_offline_timeout': r'Timeout occurred while waiting for network connectivity|systemd-networkd-wait-online.service: Failed with result|Failed to start systemd-networkd-wait-online.service',
    'unsupported_ipv6': r'Binding to IPv6 address not available since kernel does not support IPv6',
}
warning_counts = dict.fromkeys(warning_patterns, 0)
for line in c['warning_journal']['stdout'].splitlines():
    if not line.strip():
        continue
    matches = [k for k, pattern in warning_patterns.items() if re.search(pattern, line)]
    assert len(matches) == 1, 'Unclassified warning in private archive'
    warning_counts[matches[0]] += 1
journal = review['commands']['journal']['stdout']
high_signal = [line for line in journal.splitlines() if re.search(r'ERROR|CRITICAL|Traceback|segfault|EXT4-fs error|I/O error', line)]
assert len(high_signal) == 12 and all('invalid-m8d' in line and 'Got access denied for user' in line for line in high_signal)
cleanup = obj(A, 'coldboot02/cleanup.json')
assert cleanup['result'] == 'passed' and cleanup['removed'] and cleanup['bytes'] == 65536
assert cleanup['verified_sha256'] == review['persistence_sha256']
assert cleanup['root'] == '/dev/mmcblk0p1 ext4 rw,relatime'
assert cleanup['boot_id'] == review['boot_id']
print(json.dumps({'result': 'PASSED', 'phase': 'P2 attempt 02', 'candidate': 'p2-r1-candidate1',
    'enrolled_image_sha256': image, 'archives': verified, 'cold_boot_recoveries': recoveries,
    'second_cold_two_client_fps': [x['fps'] for x in video['clients']],
    'second_cold_combined_direct_reads': combined['direct_reads'], 'second_cold_browser_direct_reads': ui['direct_reads'],
    'frozen_artifacts_matched': len(review['hash_checks']), 'enrollment_files_matched': 4,
    'journal_allocation_KiB': allocation, 'expected_auth_denials': len(high_signal), 'warning_classification': warning_counts,
    'expected_offline_failed_unit': failed[0], 'persistence_cleanup': 'passed',
    'normal_reboot_full_firmware_trace': 'passed',
    'cold_boot_uart_exception': 'User-approved missing early firmware during shared power/UART re-enumeration; continuous systemd-through-recovery capture retained',
    'attempt01': 'FAILED permanently', 'candidate2': 'not required',
    'M8F_Run04': 'accepted core soak unchanged; no repeat required for network-only delta',
    'deferred': ['P3', 'M6/ATX', 'RO/overlay']}, indent=2))
