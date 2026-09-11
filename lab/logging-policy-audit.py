#!/usr/bin/env python3
"""Verify the effective logging configuration and retain runtime evidence privately."""
import configparser,json,subprocess,os
from pathlib import Path

def run(*argv):return subprocess.check_output(argv,text=True,stderr=subprocess.STDOUT)
r={'journald':run('systemd-analyze','cat-config','systemd/journald.conf'),'systemd_version':run('/usr/lib/systemd/systemd','--version'),'systemd_package':run('dpkg-query','-W','systemd'),'nginx':run('nginx','-T','-c','/etc/kvmd/nginx/nginx.conf'),'nginx_stdio':run('systemctl','show','nginx','-p','StandardOutput','-p','StandardError'),'packages':run('dpkg-query','-W','-f=${Package}\t${Version}\t${Architecture}\n'),'disk_usage':run('journalctl','--disk-usage')}
c=configparser.ConfigParser(strict=False);c.read_string(r['journald']);expected={'Storage':'volatile','RuntimeMaxUse':'16M','RuntimeMaxFileSize':'4M','Compress':'yes','ForwardToSyslog':'no'}
assert all(c['Journal'][k]==v for k,v in expected.items()),dict(c['Journal'])
assert '259.5-0ubuntu3.4' in r['systemd_package']
assert 'access_log off;' in r['nginx'] and 'error_log stderr warn;' in r['nginx']
assert 'access_log /' not in r['nginx'] and 'error_log /' not in r['nginx']
assert 'StandardOutput=journal' in r['nginx_stdio'] and any('StandardError='+s in r['nginx_stdio'] for s in ['inherit','journal'])
r['regular_log_writers']=[]
for p in Path('/proc').glob('[0-9]*/fd/*'):
 try:
  dest=str(p.readlink())
  if dest.startswith('/var/log/nginx/'):r['regular_log_writers'].append(str(p))
 except (FileNotFoundError,PermissionError,ProcessLookupError):pass
assert not r['regular_log_writers']
r['result']='passed';print(json.dumps(r,indent=2))
