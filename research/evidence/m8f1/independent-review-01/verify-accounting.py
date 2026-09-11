#!/usr/bin/env python3
"""Cross-check raw accounting identities and controller copies without analyzer imports."""
import collections,hashlib,json,pathlib,re
p=pathlib.Path('out/m8f1/review/original/observation01');out=pathlib.Path(__file__).parent
rows=[json.loads(x) for x in (p/'resources.jsonl').read_text().splitlines()];n=0;status_rollup_differences=collections.Counter()
for r in rows:
 for z in r['processes']:
  parsed={}
  for name in ['status','smaps_rollup']:
   for line in z['raw'][name].splitlines():
    words=line.split()
    if len(words)==3 and words[2]=='kB':parsed[words[0].rstrip(':')]=int(words[1])
  for k,v in parsed.items():assert v*1024==z['memory'][k+'_bytes']
  assert parsed['VmRSS']==parsed['RssAnon']+parsed['RssFile']+parsed['RssShmem']
  assert parsed['Rss']==sum(parsed[k] for k in ['Private_Clean','Private_Dirty','Shared_Clean','Shared_Dirty'])
  assert 0<=parsed['Pss']-sum(parsed[k] for k in ['Pss_Anon','Pss_File','Pss_Shmem'])<=2
  assert parsed['Pss']<=parsed['Rss'] and parsed['Anonymous']<=parsed['Rss']
  assert parsed['Swap']==0
  if parsed['VmRSS']!=parsed['Rss']:status_rollup_differences[z['comm']]+=1
  n+=1
# Verify the controller resource JSON is a faithful copy of raw command stdout.
raws={}
for f in list(p.glob('sample-*.stdout'))+[p/'baseline.stdout',p/'release-before.stdout',p/'final.stdout']:
 d=json.loads(f.read_text());raws[d['monotonic']]=d
assert len(raws)==len(rows)
for r in rows:
 assert {k:v for k,v in r.items() if k not in ['bridge_monotonic','planned','completed_cycles']}==raws[r['monotonic']]
# Journal corroboration: one stop/start of main service during captured observation.
j='\n'.join(line for line in (p/'target-journal-live.log').read_text().splitlines() if (match:=re.match(r'\[\s*([0-9.]+)\]',line)) and float(match[1])>=rows[0]['monotonic']);counts={s:j.count(s) for s in ['Stopping kvmd.service','Stopped kvmd.service','Starting kvmd.service','Started kvmd.service']};assert all(x==1 for x in counts.values()),counts
# Check all generated tables use correct raw main hourly medians via another grouping.
r=json.loads((out/'measurements.json').read_text());assert r['scope']['samples']==len(rows)
import statistics
for h in range(12):
 vals=[]
 for x in rows:
  if 106139.257735474+h*3600<=x['bridge_monotonic']<106139.257735474+(h+1)*3600:
   z=next(v for v in x['processes'] if v['pid']==889)
   vals.append(int(re.search(r'^Pss_Anon:\s+(\d+)',z['raw']['smaps_rollup'],re.M)[1]))
 assert statistics.median(vals)==r['processes']['kvmd/main: /usr|889|22446']['hourly'][h]['metrics']['Pss_Anon']['median']
report={'result':'passed','raw_process_records_checked':n,'raw_command_copies_checked':len(raws),'all_accounting_identities_pass':True,'all_swap_zero':True,'status_rollup_RSS_difference_counts':dict(status_rollup_differences),'note':'status and smaps_rollup are sequential non-atomic reads; differences are retained, not silently forced equal','journal_service_lifecycle_counts':counts,'independent_hourly_Pss_Anon_crosscheck':12}
(out/'validation.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
