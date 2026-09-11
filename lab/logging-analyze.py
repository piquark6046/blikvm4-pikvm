#!/usr/bin/env python3
"""Describe retained logging and memory; do not silently select a pass threshold."""
import argparse,collections,csv,json,pathlib,re,statistics
p=argparse.ArgumentParser();p.add_argument('root',type=pathlib.Path);p.add_argument('output',type=pathlib.Path);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
rows=[json.loads(l) for l in (a.root/'resources.jsonl').read_text().splitlines()];r=json.loads((a.root/'result.json').read_text());t0=r['start_monotonic'];series=[]
for z in rows:
 logs=z['logging'];q={'elapsed_seconds':z['bridge_monotonic']-t0,'journal_allocated':sum(f['allocated_bytes'] for f in logs['files']),'journal_files':len(logs['files']),'first_probe_present':bool(logs['first_probe']['stdout']),'processes':z['process_count'],'sockets':z['socket_count']}
 q.update({k:int(re.search(r'^'+k+r':\s+(\d+)',z['proc']['meminfo'],re.M)[1])*1024 for k in ['MemAvailable','Shmem','AnonPages','Cached','Slab','SReclaimable','SUnreclaim']})
 q.update({k:v['allocated_bytes'] for k,v in logs['directories'].items()})
 series.append(q)
def summary(v):
 return {'n':len(v),'first':v[0],'last':v[-1],'first15_median':statistics.median(v[:15]),'last15_median':statistics.median(v[-15:]),'min':min(v),'max':max(v)}
seen={};removed=[]
for z in rows:
 current={f['inode']:f for f in z['logging']['files']}
 for inode,f in seen.items():
  if inode not in current:removed.append({'elapsed_seconds':z['bridge_monotonic']-t0,'inode':inode,'last_path':f['path'],'allocated_bytes':f['allocated_bytes']})
 seen=current
first_missing=next((q['elapsed_seconds'] for q in series[1:] if not q['first_probe_present']),None)
quarter=[]
for i in range(8):
 qs=[q for q in series if i*900<=q['elapsed_seconds']<(i+1)*900]
 if qs:quarter.append({'quarter':i,'metrics':{k:summary([q[k] for q in qs]) for k in qs[0] if k not in ['elapsed_seconds','first_probe_present']}})
report={'samples':len(rows),'fixed_quota_bytes':16777216,'fixed_file_limit_bytes':4194304,'max_allocated_bytes':max(q['journal_allocated'] for q in series),'automatic_file_removals':removed,'first_probe_seen_initially':series[0]['first_probe_present'],'first_probe_absent_at_seconds':first_missing,'all_journald_healthy':all(z['logging']['health']['rc']==0 for z in rows),'all_disk_usage_commands_pass':all(z['logging']['disk_usage']['rc']==0 for z in rows),'nginx_regular_files_always_empty':all(all(v['size']==0 for v in z['logging']['nginx_logs'].values()) for z in rows),'persistent_journal_always_empty':all(q['/var/log/journal']==0 for q in series),'full':{k:summary([q[k] for q in series]) for k in series[0] if k not in ['elapsed_seconds','first_probe_present']},'quarter_hours':quarter,'decision':'independent_review_required','qualification_seconds':0}
(a.output/'logging-analysis.json').write_text(json.dumps(report,indent=2)+'\n')
with (a.output/'logging-series.csv').open('w') as f:w=csv.DictWriter(f,fieldnames=list(series[0]),lineterminator="\n");w.writeheader();w.writerows(series)
print(json.dumps({k:v for k,v in report.items() if k not in ['full','quarter_hours','automatic_file_removals']},indent=2))
