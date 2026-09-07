#!/usr/bin/env python3
"""Target-local, read-only M8-C inventory; emits no credential or key contents."""
import hashlib
import ipaddress
import json
from pathlib import Path
import socket
import subprocess


def run(*args):
    p = subprocess.run(args, capture_output=True, text=True, timeout=30)
    if p.returncode:
        raise RuntimeError(str(args)+': '+p.stderr)
    return p.stdout


result = {'result': 'failed', 'logs': {}}
try:
    result['boot_id'] = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    logs = result['logs']
    logs['nginx-effective'] = run('nginx', '-T', '-c', '/etc/kvmd/nginx/nginx.conf')
    logs['listeners-ss'] = run('ss', '-lntup')
    logs['unix-sockets'] = run('ss', '-lxnp')
    listeners = []
    for version in (4, 6):
        p = Path('/proc/net/tcp'+('6' if version == 6 else ''))
        if not p.exists():
            continue
        for line in p.read_text().splitlines()[1:]:
            fields = line.split()
            if fields[3] != '0A':
                continue
            address, port = fields[1].split(':')
            data = bytes.fromhex(address)
            data = b''.join(data[i:i+4][::-1] for i in range(0, len(data), 4))
            listeners.append({'address': str(ipaddress.ip_address(data)), 'port': int(port, 16)})
    result['listeners_proc'] = listeners
    assert sorted((x['address'],x['port']) for x in listeners) == [
        ('192.168.88.2', 22), ('192.168.88.2', 443)], listeners
    for name in ('nginx', 'kvmd', 'ssh', 'blikvm-access'):
        assert run('systemctl', 'is-active', name).strip() == 'active'
        logs[name+'-unit'] = run('systemctl', 'cat', name)
    assert run('systemctl', 'is-enabled', 'nginx').strip() == 'enabled'
    assert run('systemctl', 'is-enabled', 'kvmd').strip() == 'enabled'
    logs['systemd-failed'] = run('systemctl', '--failed', '--no-pager')
    assert not run('systemctl', '--failed', '--no-legend', '--plain').strip()
    main = int(run('systemctl', 'show', 'kvmd', '-p', 'MainPID', '--value'))
    children = []
    for p in Path('/proc').glob('[0-9]*/exe'):
        try:
            if p.readlink() != Path('/usr/bin/ustreamer'):
                continue
            fields = dict(line.split(':', 1) for line in (p.parent/'status').read_text().splitlines() if ':' in line)
            child = {'pid': int(p.parent.name), 'ppid': int(fields['PPid']),
                     'uid': fields['Uid'].strip(), 'gid': fields['Gid'].strip(),
                     'cmdline': (p.parent/'cmdline').read_bytes().replace(b'\0', b' ').decode(),
                     'cgroup': (p.parent/'cgroup').read_text()}
            children.append(child)
        except (FileNotFoundError, ProcessLookupError):
            pass
    assert len(children) == 1, children
    assert children[0]['ppid'] == main
    result['kvmd_pid'] = main
    result['ustreamer'] = children[0]
    result['ustreamer_version'] = run('dpkg-query', '-W', '-f=${Version}', 'ustreamer')
    assert result['ustreamer_version'] == '6.65-1blikvm2'
    digest = hashlib.sha256(Path('/usr/bin/ustreamer').read_bytes()).hexdigest()
    assert digest == 'e5a489c828299bc28de71789414312510198c6d7da63b2b18c300bef6313e71b'
    result['ustreamer_sha256'] = digest
    logs['auth-config'] = Path('/etc/kvmd/override.d/80-web-auth.yaml').read_text()
    logs['kvmd-effective'] = run('/usr/bin/kvmd', '--dump-config')
    logs['socket-acls'] = run('getfacl', '-p', '/run/kvmd', '/run/kvmd/api',
                              '/run/kvmd/api/kvmd.sock', '/run/kvmd/ustreamer',
                              '/run/kvmd/ustreamer/ustreamer.sock')
    for dev in ('/dev/kvmd-video', '/dev/hidg0', '/dev/hidg1', '/dev/hidg2', '/dev/gpiochip0'):
        if Path(dev).exists():
            assert subprocess.run(['runuser','-u','www-data','--','test','-r',dev]).returncode != 0
            assert subprocess.run(['runuser','-u','www-data','--','test','-w',dev]).returncode != 0
    logs['video-mode'] = run('v4l2-ctl', '-d', '/dev/kvmd-video', '--get-fmt-video', '--get-parm')
    for value in ('1920/1080', "'MJPG'", '30.000 (30/1)'):
        assert value in logs['video-mode'], logs['video-mode']
    logs['tls-public'] = run('openssl', 'x509', '-in', '/etc/kvmd/nginx/ssl/server.crt',
                             '-noout', '-subject', '-issuer', '-dates', '-fingerprint', '-sha256')
    logs['nginx-journal'] = run('journalctl', '-b', '-u', 'nginx', '--no-pager')
    logs['kvmd-journal'] = run('journalctl', '-b', '-u', 'kvmd', '--no-pager')
    logs['target-dmesg'] = run('dmesg')
    import re
    assert not re.search(r'uvcvideo[^\n]*(?:Failed|failed|error)|usb 1-1[^\n]*(?:disconnect|reset high-speed)', logs['target-dmesg']), 'UVC error in boot journal'
    logs['nginx-error'] = Path('/var/log/nginx/error.log').read_text()
    logs['nginx-access'] = Path('/var/log/nginx/access.log').read_text()
    logs['firewall-effective'] = run('nft', '-j', 'list', 'ruleset')
    logs['firewall-text'] = run('nft', 'list', 'ruleset')
    logs['firewall-unit'] = run('systemctl', 'cat', 'blikvm-access')
    logs['firewall-config'] = Path('/etc/kvmd/access.nft').read_text()
    for name in ('tcp', 'tcp6'):
        p = Path('/proc/net')/name
        logs['proc-net-'+name] = p.read_text() if p.exists() else 'absent'
    assert not Path('/proc/net/if_inet6').exists(), 'IPv6 must remain disabled'
    assert run('systemctl', 'is-enabled', 'blikvm-access').strip() == 'enabled'
    def canonical(value):
        if isinstance(value, list):
            return [canonical(x) for x in value if 'metainfo' not in x]
        if isinstance(value, dict):
            return {k:canonical(v) for k,v in value.items() if k not in ('handle','packets','bytes')}
        return value
    expected = {'nftables': [{'metainfo': {'version': '1.1.6', 'release_name': 'Commodore Bullmoose #7', 'json_schema_version': 1}}, {'table': {'family': 'ip', 'name': 'blikvm_lab', 'handle': 2}}, {'chain': {'family': 'ip', 'table': 'blikvm_lab', 'name': 'input', 'handle': 1, 'type': 'filter', 'hook': 'input', 'prio': 0, 'policy': 'drop'}}, {'chain': {'family': 'ip', 'table': 'blikvm_lab', 'name': 'forward', 'handle': 2, 'type': 'filter', 'hook': 'forward', 'prio': 0, 'policy': 'drop'}}, {'rule': {'family': 'ip', 'table': 'blikvm_lab', 'chain': 'input', 'handle': 10, 'expr': [{'match': {'op': '==', 'left': {'meta': {'key': 'iifname'}}, 'right': 'eth0'}}, {'match': {'op': '==', 'left': {'payload': {'protocol': 'ip', 'field': 'saddr'}}, 'right': '192.168.88.1'}}, {'match': {'op': '==', 'left': {'payload': {'protocol': 'ip', 'field': 'daddr'}}, 'right': '192.168.88.2'}}, {'match': {'op': '==', 'left': {'payload': {'protocol': 'tcp', 'field': 'dport'}}, 'right': 443}}, {'counter': {'packets': 0, 'bytes': 0}}, {'accept': None}]}}, {'rule': {'family': 'ip', 'table': 'blikvm_lab', 'chain': 'input', 'handle': 11, 'expr': [{'match': {'op': '==', 'left': {'payload': {'protocol': 'tcp', 'field': 'dport'}}, 'right': 443}}, {'counter': {'packets': 0, 'bytes': 0}}, {'drop': None}]}}, {'rule': {'family': 'ip', 'table': 'blikvm_lab', 'chain': 'input', 'handle': 12, 'expr': [{'match': {'op': '==', 'left': {'payload': {'protocol': 'tcp', 'field': 'dport'}}, 'right': 80}}, {'counter': {'packets': 0, 'bytes': 0}}, {'drop': None}]}}, {'rule': {'family': 'ip', 'table': 'blikvm_lab', 'chain': 'input', 'handle': 13, 'expr': [{'match': {'op': '==', 'left': {'meta': {'key': 'iifname'}}, 'right': 'lo'}}, {'counter': {'packets': 0, 'bytes': 0}}, {'accept': None}]}}, {'rule': {'family': 'ip', 'table': 'blikvm_lab', 'chain': 'input', 'handle': 14, 'expr': [{'match': {'op': '==', 'left': {'meta': {'key': 'iifname'}}, 'right': 'eth0'}}, {'match': {'op': '==', 'left': {'payload': {'protocol': 'ip', 'field': 'saddr'}}, 'right': '192.168.88.1'}}, {'match': {'op': '==', 'left': {'payload': {'protocol': 'ip', 'field': 'daddr'}}, 'right': '192.168.88.2'}}, {'match': {'op': '==', 'left': {'payload': {'protocol': 'tcp', 'field': 'dport'}}, 'right': 22}}, {'counter': {'packets': 0, 'bytes': 0}}, {'accept': None}]}}, {'rule': {'family': 'ip', 'table': 'blikvm_lab', 'chain': 'input', 'handle': 15, 'expr': [{'match': {'op': '==', 'left': {'meta': {'key': 'iifname'}}, 'right': 'eth0'}}, {'match': {'op': '==', 'left': {'payload': {'protocol': 'ip', 'field': 'saddr'}}, 'right': '192.168.88.1'}}, {'match': {'op': '==', 'left': {'payload': {'protocol': 'ip', 'field': 'daddr'}}, 'right': '192.168.88.2'}}, {'match': {'op': '==', 'left': {'payload': {'protocol': 'ip', 'field': 'protocol'}}, 'right': 'icmp'}}, {'counter': {'packets': 0, 'bytes': 0}}, {'accept': None}]}}, {'rule': {'family': 'ip', 'table': 'blikvm_lab', 'chain': 'input', 'handle': 16, 'expr': [{'counter': {'packets': 0, 'bytes': 0}}, {'drop': None}]}}]}
    assert canonical(json.loads(logs['firewall-effective'])) == canonical(expected), 'effective policy mismatch'
    assert hashlib.sha256(logs['firewall-config'].encode()).hexdigest() == '9a77cc190bbb38ff15265905b3f31c258bd384a65decba324bc8dbc8293916b5'
    assert 'listen 192.168.88.2:443 ssl;' in logs['nginx-effective']
    import re
    assert re.findall(r'^\s*listen\s+([^;]+);', logs['nginx-effective'], re.M) == ['192.168.88.2:443 ssl']
    assert run('dpkg-query', '-W', '-f=${Version}', 'kvmd-web') == '4.213-1blikvm2'
    result['result'] = 'passed'
except Exception as error:
    result['error'] = str(error)
print(json.dumps(result))
raise SystemExit(result['result'] != 'passed')
