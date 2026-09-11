#!/usr/bin/env python3
"""M8-F2 minute snapshot: no vacuum, rotation, cache dropping or application change."""
import json,os,subprocess,time
from pathlib import Path
ns={'__name__':'logging_base'};exec(compile(BASE_SOURCE,'soak-resources.py','exec'),ns)
r=ns['sample']()
def command(argv):
 p=subprocess.run(argv,capture_output=True,text=True,timeout=20);return {'rc':p.returncode,'stdout':p.stdout,'stderr':p.stderr}
r['logging']={'disk_usage':command(['journalctl','--disk-usage']), 'health':command(['systemctl','is-active','systemd-journald']), 'files':[], 'directories':{}}
for name in ['/var/log','/var/log/journal','/run/log/journal','/var/log/nginx']:
 p=Path(name)
 d=command(['du','-sx','-B1',name]) if p.exists() else None
 r['logging']['directories'][name]={'exists':p.exists(),'allocated_bytes':int(d['stdout'].split()[0]) if d and d['rc']==0 else 0,'du':d}
 if 'journal' in name and p.exists():
  for f in sorted(p.rglob('*')):
   if f.is_file():
    s=f.stat();r['logging']['files'].append({'path':str(f),'inode':s.st_ino,'size':s.st_size,'allocated_bytes':s.st_blocks*512})
p=subprocess.Popen(['journalctl','-b','-o','json','--no-pager'],stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True)
try:
 r['logging']['oldest_json']=p.stdout.readline().strip()
finally:
 p.terminate();p.wait(timeout=10);p.stdout.close()
r['logging']['first_probe']=command(['journalctl','-b','-t','m8f2-retention','--grep=^probe=0000000000 ','-o','json','--no-pager'])
r['logging']['nginx_logs']={str(p):{'size':p.stat().st_size,'allocated_bytes':p.stat().st_blocks*512} for p in Path('/var/log/nginx').glob('*') if p.is_file()}
r['logging']['process_memory']=[]
for p in Path('/proc').glob('[0-9]*'):
 try:
  comm=(p/'comm').read_text().strip()
  if comm not in ['systemd-journal','nginx','main'] and not comm.startswith('kvmd'):continue
  z={'pid':int(p.name),'comm':comm,'status':(p/'status').read_text()}
  try:z['smaps_rollup']=(p/'smaps_rollup').read_text()
  except (FileNotFoundError,PermissionError):z['smaps_rollup']=None
  r['logging']['process_memory'].append(z)
 except (FileNotFoundError,ProcessLookupError):pass
print(json.dumps(r))
