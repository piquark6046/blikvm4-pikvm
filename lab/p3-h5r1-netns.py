#!/usr/bin/env python3
"""Authoritative pre-drop netlink gate, shared by VM regression and bridge."""
import ipaddress
import json
import os
from pathlib import Path
import subprocess


def observe(host_netns):
    raw = {}
    commands = {
        'lo_up': ['link', 'set', 'lo', 'up'],
        'link': ['-j', 'link', 'show'],
        'addr': ['-j', 'addr', 'show'],
        'route': ['-j', 'route', 'show'],
        'route_all': ['-j', 'route', 'show', 'table', 'all'],
        'route6': ['-6', '-j', 'route', 'show', 'table', 'all'],
        'target_route': ['route', 'get', '192.168.88.2'],
    }
    for name, args in commands.items():
        p = subprocess.run(['/usr/sbin/ip', *args], capture_output=True, text=True,
                           env={'PATH':'/usr/bin:/bin', 'LANG':'C'})
        raw[name] = dict(args=args, returncode=p.returncode, stdout=p.stdout, stderr=p.stderr)
    sockets = []
    for fd in Path('/proc/self/fd').iterdir():
        try:
            target = os.readlink(fd)
        except FileNotFoundError:
            continue
        if target.startswith('socket:'):
            sockets.append({'fd':fd.name, 'target':target})
    return {'host_netns':host_netns, 'netns':os.readlink('/proc/self/ns/net'),
            'raw':raw, 'sockets':sockets}


def validate(r):
    def require(ok, why):
        if not ok:
            raise RuntimeError(why)
    require(r['netns'] != r['host_netns'], 'host network namespace retained')
    raw = r['raw']
    for name, p in raw.items():
        if name != 'target_route':
            require(p['returncode'] == 0, name+' command failed')
    require([x['ifname'] for x in json.loads(raw['link']['stdout'])] == ['lo'], 'external link')
    addresses = json.loads(raw['addr']['stdout'])
    require([x['ifname'] for x in addresses] == ['lo'], 'external address interface')
    require(bool(addresses[0]['addr_info']), 'loopback addresses absent')
    require(all(ipaddress.ip_address(a['local']).is_loopback for x in addresses for a in x['addr_info']), 'external address')
    for name in ('route', 'route_all', 'route6'):
        require(all(x.get('dev') == 'lo' and not x.get('gateway') for x in json.loads(raw[name]['stdout'])), 'external route')
    require(raw['target_route']['returncode'] != 0 and 'Network is unreachable' in raw['target_route']['stderr'], 'target route not unreachable')
    require(not r['sockets'], 'inherited socket present')
