#!/usr/bin/env python3
"""Target-local, read-only M8-B inventory; emits no credential or key contents."""
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
        ('127.0.0.1', 443), ('192.168.88.2', 22)], listeners
    for name in ('nginx', 'kvmd', 'ssh'):
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
    logs['nginx-error'] = Path('/var/log/nginx/error.log').read_text()
    logs['nginx-access'] = Path('/var/log/nginx/access.log').read_text()
    result['result'] = 'passed'
except Exception as error:
    result['error'] = str(error)
print(json.dumps(result))
raise SystemExit(result['result'] != 'passed')
