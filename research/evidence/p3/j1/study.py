#!/usr/bin/env python3
"""Offline, unclassified timelines from hash-pinned private archives. No extraction."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import tarfile

ROOT = Path(__file__).resolve().parents[4]
CORPUS = [
 ('h5r2-functional-001','out/p3-h5r2/functional-001.tar.gz','4cf2e4f9b890639d2f832b3dc917b4f52ab6d67c28c6a37e6a6755d4fa7fe627','controller/functional-001/after/target.json','journal_json'),
 ('h5r2-functional-002','out/p3-h5r2/functional-002.tar.gz','6073424557af5d67d813da1fddc1aa968fd31907e4d68daba999af3d430de707','controller/functional-002/after/target.json','journal_json'),
 ('h5r2-functional-003','out/p3-h5r2/functional-003.tar.gz','830608ff1f8f5b398b88f1c64cdbb320f38961ee602f3caf2f8108982314c1e6','controller/functional-003/after/target.json','journal_json'),
 ('a01-cycle-001','out/p3/preparation/a01-evidence.tar.gz','dde56c3bf3ab1d14006c601c8c8a05343c353b11c385f9b8a33755837ed5e57a','cycle/failure-preservation/target.json','journal_json'),
 ('a03-cycle-001','out/p3-controller-r1/p3-a03-cycle-001.tar.gz','58ef027fa82066b505827133b488005aa22d4d15f543b8a73ab96715e02abccb','controller/p3-a03-cycle-001/after/target.json','journal_json'),
 ('p2-accepted-a01-preboot','out/p3/preparation/a01-evidence.tar.gz','dde56c3bf3ab1d14006c601c8c8a05343c353b11c385f9b8a33755837ed5e57a','cycle/before/target.json','journal_json'),
 ('p2-normal-reboot','out/p2/attempt02-preparation/normal-reboot-evidence.tar.gz','65e68116534a5ba6fe6b3ba4f038c13739f0074bce42d242b9fc86043f93fbfc','snapshot/after.json','journal'),
 ('p2-final-coldboot','out/p2/attempt02-preparation/final-evidence.tar.gz','1cbc3e9d529fb23b045750219d2a1e7de57e89713fe4c553adf24993484b7b08','coldboot02/final-review.json','journal'),
]
SIGNAL = re.compile(r'\bERROR\b|\bCRITICAL\b|Traceback|\[error\]|\[crit\]|segfault|EXT4-fs error|I/O error|Buffer I/O|Kernel panic|Oops:|checksum error')

def load(spec):
 name,path,digest,member,key=spec
 with (ROOT/path).open('rb') as f:
  if hashlib.file_digest(f,'sha256').hexdigest()!=digest:raise ValueError('archive identity: '+name)
 with tarfile.open(ROOT/path) as t:
  matches=[m for m in t if m.name==member]
  if len(matches)!=1 or not matches[0].isfile():raise ValueError('ambiguous member')
  raw=t.extractfile(matches[0]).read();inv=json.loads(raw)
 command=inv['commands'][key]
 if command.get('returncode',0)!=0:raise ValueError('failed journal collection')
 text=command['stdout'];rows=[]
 for i,line in enumerate(text.splitlines()):
  if key=='journal_json':r=json.loads(line)
  else:
   m=re.fullmatch(r'\[\s*(\d+)\.(\d{6})\] (\S+) ([^:]+): (.*)',line)
   if not m:raise ValueError(('unparsed text journal',name,i))
   sec,us,host,ident,msg=m.groups()
   r={'__MONOTONIC_TIMESTAMP':str(int(sec)*1000000+int(us)),'MESSAGE':msg,'SYSLOG_IDENTIFIER':ident,'_BOOT_ID':inv['boot_id'].replace('-','')}
   # Text journals do NOT establish trusted unit or priority fields.
  rows.append(r)
 return inv,rows,{'name':name,'archive':path,'archive_sha256':digest,'member':member,'member_sha256':hashlib.sha256(raw).hexdigest(),'journal_sha256':hashlib.sha256(text.encode()).hexdigest(),'format':key,'records':len(rows),'boot_id':inv['boot_id']}

def timeline(rows):
 out=[]
 for i,r in enumerate(rows):
  msg=str(r.get('MESSAGE',''));unit=r.get('_SYSTEMD_UNIT');ident=r.get('SYSLOG_IDENTIFIER','')
  candidate=bool(SIGNAL.search(msg)) or int(r.get('PRIORITY',6))<=3
  if candidate or unit in ('init.scope','kvmd.service','nginx.service') or ident.startswith(('systemd','kvmd','nginx')) or 'kvmd.sock' in msg:
   out.append({'record_index':i,'timestamp_us':int(r['__MONOTONIC_TIMESTAMP']),'unit':unit,'priority':r.get('PRIORITY'),'message':msg,'error_candidate':candidate,'raw_record':r})
 return out

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('output',type=Path);a=p.parse_args();a.output.mkdir(mode=0o700,parents=True,exist_ok=True)
 summaries=[]
 for spec in CORPUS:
  inv,rows,meta=load(spec);doc={**meta,'classification_performed':False,'timeline':timeline(rows)}
  with (a.output/(spec[0]+'.json')).open('x') as f:json.dump(doc,f,indent=2);f.write('\n')
  summaries.append(meta)
 print(json.dumps(summaries,indent=2))
