#!/usr/bin/env python3
"""Review immutable retention journal, source identities, and allocation accounting."""
import argparse,collections,hashlib,json,pathlib,re,statistics
p=argparse.ArgumentParser();p.add_argument('root',type=pathlib.Path);p.add_argument('output',type=pathlib.Path);a=p.parse_args();root=a.root;out=a.output;out.mkdir(exist_ok=True,parents=True)
r=json.loads((root/'result.json').read_text());rows=[json.loads(l) for l in (root/'resources.jsonl').read_text().splitlines()];start=r['start_monotonic'];cycles=r['cycles']
read=lambda n:json.loads((root/n).read_text())
old=pathlib.Path('out/m8f1/review/original/observation01')
workers=['soak-video.py','soak-browser.mjs','stream-client.py','hid-api-hil.py','msd-hil.py','msd-workload.py']
for name in workers:assert (root/'automation'/name).read_bytes()==(old/'automation'/name).read_bytes(),name
raws={}
for f in list(root.glob('sample-*.stdout'))+[root/'baseline.stdout',root/'final.stdout']:
 z=json.loads(f.read_text());raws[z['monotonic']]=z
for z in rows:assert raws[z['monotonic']]=={k:v for k,v in z.items() if k not in ['bridge_monotonic','planned','completed_cycles']}
def bridge_time(t):
 z=min(rows,key=lambda z:abs(z['monotonic']-t));return t+z['bridge_monotonic']-z['monotonic']
def in_cycle(t):return any(c['start']<=t<=c['end'] for c in cycles)
j=(root/'target-journal-live.log').read_text().splitlines();counts=collections.Counter();bytes_by_id=collections.Counter();auth=[];http=[];unknown=[];probes=[]
for line in j:
 m=re.match(r'\[\s*([0-9.]+)\] \S+ ([^:]+): (.*)',line);assert m,line[:100]
 t=float(m[1]);id=re.sub(r'\[\d+\]$','',m[2]);msg=m[3];counts[id]+=1;bytes_by_id[id]+=len(line.encode())+1
 if id=='m8f2-retention':
  k=re.match(r'probe=(\d+) payload=[0-9a-f]{384}$',msg);assert k;probes.append(int(k[1]))
 if re.search(r'error|fail|timeout|timed out|reset|stall|BUG:|Oops|traceback|out of memory|suppress|dropped',line,re.I):
  if "Got access denied for user 'invalid-m8d'" in msg:
   assert in_cycle(bridge_time(t));auth.append(t)
  elif 'aiohttp.access' in msg and 'HTTP/1.1' in msg:
   assert in_cycle(bridge_time(t));k=re.search(r"'(\w+) ([^ ]+) HTTP/1.1' => (\d+)",msg);assert k;http.append(' '.join(k.groups()))
  else:unknown.append(line)
assert not unknown,'Unclassified target journal candidates'
assert len(auth)==len(cycles)==23
assert len(probes)>230000 and probes==list(range(probes[-1]+1)), 'missing or reordered load probes'
# SCSI failure stanzas must correspond exactly to intentional ejection windows.
host=(root/'host-kernel-live.log').read_text().splitlines();scsi=[];unclassified=[];wifi=0
for i,line in enumerate(host):
 if 'FAILED Result:' in line:
  stanza=host[i:i+5];assert len(stanza)==5 and 'Sense Key : Not Ready' in stanza[1] and 'Medium not present' in stanza[2] and 'CDB: Read(10)' in stanza[3] and 'I/O error, dev sda' in stanza[4]
  t=float(re.match(r'\[\s*([0-9.]+)\]',line)[1]);assert in_cycle(t);scsi.append(t)
 elif re.search(r'error|fail|timeout|timed out|reset|stall|BUG:|Oops|traceback|out of memory|suppress|dropped',line,re.I) and 'I/O error, dev sda' not in line:unclassified.append(line)
 if 'wlo1:' in line:wifi+=1
assert len(scsi)==23 and not unclassified
allocation_differences=collections.Counter();oldest=[]
for z in rows:
 logs=z['logging'];files=logs['files'];allocation_differences[logs['directories']['/run/log/journal']['allocated_bytes']-sum(f['allocated_bytes'] for f in files)]+=1
 assert sum(f['allocated_bytes'] for f in files)<=16777216
 assert all(f['allocated_bytes']<=4194304 for f in files)
 q=json.loads(logs['oldest_json']);oldest.append(int(q['__MONOTONIC_TIMESTAMP']))
assert oldest[-1]>oldest[0]
contracts=['kvmd-unit','nginx-unit','auth-config','kvmd-effective','gadget-owner-unit','firewall-config','firewall-unit','blikvm-access-unit']
for side in ['before','after']:
 audit=read('logging-policy-'+side+'.stdout');assert audit['packages']==pathlib.Path('out/kvmd-msd/artifacts/packages.tsv').read_text();assert not audit['regular_log_writers']
 inv=read('inventory-'+side+'.stdout');orig=json.loads((old/'inventory-before.stdout').read_text())
 assert all(inv['logs'][k]==orig['logs'][k] for k in contracts)
 expected=orig['logs']['nginx-effective'].replace('error_log /var/log/nginx/error.log warn;','error_log stderr warn;').replace('access_log /var/log/nginx/access.log combined;','access_log off;');assert inv['logs']['nginx-effective']==expected
report={'result':'passed','raw_sample_copies_checked':len(rows),'frozen_workers':workers,'frozen_contracts':contracts,'journal_generators':{k:{'messages':v,'rendered_bytes':bytes_by_id[k]} for k,v in counts.most_common()},'load_probe_count':len(probes),'load_probe_sequences_contiguous_from_zero':True,'expected_auth_negative_errors':len(auth),'expected_http_candidates':dict(collections.Counter(http)),'expected_ejected_medium_scsi_stanzas':len(scsi),'host_wifi_messages':wifi,'unclassified_candidates':0,'directory_minus_file_allocation_histogram':dict(allocation_differences),'max_individual_journal_allocated_bytes':max(f['allocated_bytes'] for z in rows for f in z['logging']['files']),'oldest_retained_entry_advanced_seconds':(oldest[-1]-oldest[0])/1e6,'PSS_available_samples':sum(any(p['smaps_rollup'] is not None for p in z['logging']['process_memory']) for z in rows),'manual_vacuum_or_rotation_commands_in_controller':False,'note':'No manual retention action was issued; archived controller and load sources are preserved for inspection. Per-minute observations cannot exclude arbitrarily short unsampled resource peaks.'}
(out/'review.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
