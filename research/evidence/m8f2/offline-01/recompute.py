#!/usr/bin/env python3
"""M8-F2 attribution from immutable M8-F1 raw samples and journal text only."""
import collections,csv,hashlib,json,math,pathlib,re,statistics,tarfile
root=pathlib.Path('out/m8f1/review'); src=root/'original/observation01'; out=pathlib.Path(__file__).parent
sha=lambda b:hashlib.sha256(b).hexdigest()
assert sha((root/'observation01-private.tar.gz').read_bytes())=='1cbe958805a2a10763143be662ef0988486d4867e488cd8a3a032a3cd553957b'
idx=json.loads((root/'observation01-files.json').read_text())
with tarfile.open(root/'observation01-private.tar.gz') as tar:
 members={m.name:m for m in tar if m.isfile()}
 for f in idx:
  b=(src/f['path']).read_bytes(); assert len(b)==f['bytes'] and sha(b)==f['sha256']
  matches=[n for n in members if n.endswith('/observation01/'+f['path']) or n=='observation01/'+f['path']]; assert len(matches)==1
  assert sha(tar.extractfile(members[matches[0]]).read())==sha(b)
controller=[json.loads(l) for l in (src/'resources.jsonl').read_text().splitlines()]
raw={}
for p in list(src.glob('sample-*.stdout'))+[src/'baseline.stdout',src/'release-before.stdout',src/'final.stdout']:
 r=json.loads(p.read_text());raw[r['monotonic']]=r
assert len(raw)==len(controller)==737
result=json.loads((src/'result.json').read_text());t0=result['start_monotonic']; rows=[]
paths=['/var/log','/var/log/journal','/run/log/journal','/var/log/nginx']; keys=paths+['Shmem','MemAvailable']
for c in controller:
 r=raw[c['monotonic']];assert r=={k:v for k,v in c.items() if k not in ['bridge_monotonic','planned','completed_cycles']}
 z={'elapsed_h':(c['bridge_monotonic']-t0)/3600,'monotonic':r['monotonic'],'cycles':c['completed_cycles']}
 for k in paths:
  assert r['runtime_usage'][k]['du_rc']==0;z[k]=r['runtime_usage'][k]['allocated_bytes']
 for k in keys[4:]:z[k]=int(re.search(r'^'+k+r':\s+(\d+) kB$',r['proc']['meminfo'],re.M)[1])*1024
 rows.append(z)
def stats(rs,k):
 v=[r[k] for r in rs];ts=[r['elapsed_h'] for r in rs];xm=statistics.mean(ts);ym=statistics.mean(v);den=sum((t-xm)**2 for t in ts)
 return {'samples':len(rs),'initial_bytes':v[0],'final_bytes':v[-1],'delta_bytes':v[-1]-v[0],'median_bytes':statistics.median(v),'ols_bytes_per_hour':sum((t-xm)*(y-ym) for t,y in zip(ts,v))/den if den else None,'decreases':sum(b<a for a,b in zip(v,v[1:])),'increases':sum(b>a for a,b in zip(v,v[1:])),'nondecreasing':all(b>=a for a,b in zip(v,v[1:]))}
# Independently identify the old main generation's terminal Pss_Anon constant run.
pre=[c for c in controller if c['bridge_monotonic']<result['events'][0]['start']]
v=[int(re.search(r'^Pss_Anon:\s+(\d+)',next(p for p in raw[c['monotonic']]['processes'] if p['pid']==889)['raw']['smaps_rollup'],re.M)[1]) for c in pre]
i=len(v)-1
while i and v[i-1]==v[-1]:i-=1
terminal=rows[i:len(pre)];first=[r for r in terminal if r['elapsed_h']<terminal[0]['elapsed_h']+.25];last=[r for r in terminal if r['elapsed_h']>=terminal[-1]['elapsed_h']-.25]
terminal_delta={k:statistics.median(r[k] for r in last)-statistics.median(r[k] for r in first) for k in keys}
assert terminal_delta['/var/log']==terminal_delta['/var/log/journal']+terminal_delta['/var/log/nginx']==terminal_delta['Shmem']==6725632
residuals=collections.Counter(r['/var/log']-r['/var/log/journal']-r['/var/log/nginx'] for r in rows)
# Short-monotonic rendering preserves identifiers but not structured unit fields.
entries=[];unparsed=0
for line in (src/'target-journal-live.log').read_text().splitlines(keepends=True):
 m=re.match(r'\[\s*([0-9.]+)\] \S+ ([^:]+): (.*)',line)
 if not m:unparsed+=1;continue
 t=float(m[1])
 if rows[0]['monotonic']<=t<=rows[-1]['monotonic']:
  entries.append({'t':t,'id':re.sub(r'\[\d+\]$','',m[2]),'bytes':len(line.encode()),'message':m[3]})
def counts(es):
 d={}
 for e in es:
  v=d.setdefault(e['id'],{'count':0,'rendered_bytes':0});v['count']+=1;v['rendered_bytes']+=e['bytes']
 return dict(sorted(d.items(),key=lambda x:-x[1]['count']))
# Associate short-lived SSH sessions with a sample by the sudo session that encloses it.
sudo={}
for e in entries:
 if e['id']=='sudo' and 'COMMAND=/usr/bin/python3 -' in e['message']:sudo[e['t']]=e
near=[]
for c in controller:
 r=raw[c['monotonic']];a=r['monotonic']-2;b=r['monotonic']+r['sampling_seconds']+2
 near.append([e for e in entries if a<=e['t']<=b and e['id'] in ['sudo','sshd-session','unix_chkpwd']])
near_unique={ (e['t'],e['id'],e['message']):e for es in near for e in es }
# Complete nginx files were embedded in endpoint inventories. Preserve only categories/counts.
before=json.loads((src/'inventory-before.stdout').read_text())['logs'];after=json.loads((src/'inventory-after.stdout').read_text())['logs']
access_before=before['nginx-access'];access_after=after['nginx-access'];assert access_after.startswith(access_before)
new_access=access_after[len(access_before):]; request_counts=collections.Counter();agent_counts=collections.Counter()
for l in new_access.splitlines():
 m=re.search(r'"([A-Z]+) ([^ ?]+)(?:\?[^ ]*)? HTTP/[^\"]+" (\d+) .* "([^\"]*)"$',l)
 if m:request_counts[m[1]+' '+m[2]+' '+m[3]]+=1;agent_counts[m[4]]+=1
jumps=[{'elapsed_h':r['elapsed_h'],'delta_bytes':r['/var/log/journal']-p['/var/log/journal']} for p,r in zip(rows,rows[1:]) if r['/var/log/journal']!=p['/var/log/journal']]
report={'archive_sha256':sha((root/'observation01-private.tar.gz').read_bytes()),'files_verified':len(idx),'samples':len(rows),'directory_residual_histogram_bytes':dict(residuals),'units':'bytes; OLS slopes bytes/hour; half-open elapsed-hour bins; last bin partial','full':{k:stats(rows,k) for k in keys},'hourly':[{ 'hour':h,'metrics':{k:stats([r for r in rows if h<=r['elapsed_h']<h+1],k) for k in keys}} for h in range(math.floor(rows[-1]['elapsed_h'])+1)],'terminal':{'start_elapsed_h':terminal[0]['elapsed_h'],'samples':len(terminal),'first_edge_samples':len(first),'last_edge_samples':len(last),'first_last_15m_median_delta_bytes':terminal_delta},'journal':{'grouping':'rendered SYSLOG_IDENTIFIER-like prefix; _SYSTEMD_UNIT fields not archived','generators':counts(entries),'messages':len(entries),'unparsed_lines':unparsed,'sampler_nearby_admin':counts(list(near_unique.values())),'sampler_association':'within 2 seconds before target sample start through duration plus 2 seconds; temporal association, not exclusive causal assignment','rotation_drop_mentions':sum(bool(re.search(r'rotat|vacuum|suppress|dropped',e['message'],re.I)) for e in entries),'allocation_steps':jumps,'rotation_conclusion':'No aggregate decrease or rotation/drop message observed. No per-file journal identities archived: rotation without net decrease cannot be excluded; bound not demonstrated.'},'nginx':{'endpoint_access_append_only':True,'new_access_lines':len(new_access.splitlines()),'new_access_serialized_bytes':len(new_access.encode()),'request_categories':dict(request_counts.most_common()),'agents':dict(agent_counts.most_common()),'error_bytes_before':len(before['nginx-error'].encode()),'error_bytes_after':len(after['nginx-error'].encode()),'time_caveat':'endpoint inventories extend beyond resource endpoints; target wall clock differs from bridge UTC; do not directly compare their timestamps','rotation_conclusion':'Endpoint access content has the complete earlier prefix; directory allocations never decrease. No access truncation demonstrated; no journal file inventory.'},'qualification_seconds':0}
(out/'measurements.json').write_text(json.dumps(report,indent=2)+'\n')
with (out/'series.csv').open('w') as f:
 w=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator="\n");w.writeheader();w.writerows(rows)
text=['# M8-F2 offline attribution','', 'All 737 raw command samples independently matched to controller records; all 6,393 archive members rehashed. Original archive unchanged. Allocation bytes, not apparent file length. Shmem and MemAvailable are system counters; overlapping classes are not summed.','', '| Metric | Initial bytes | Final bytes | Delta bytes | Nondecreasing |','| --- | ---: | ---: | ---: | --- |']
for k,s in report['full'].items():text.append(f"| {k} | {s['initial_bytes']} | {s['final_bytes']} | {s['delta_bytes']} | {s['nondecreasing']} |")
text+=['','## Hourly medians and growth','', 'OLS growth within each hour is descriptive, not a pass threshold. Hour 12 is partial and includes the scheduled restart.','', '| Hour | Metric | Median bytes | OLS bytes/hour | Endpoint delta bytes |','| --- | --- | ---: | ---: | ---: |']
for h in report['hourly']:
 for k,s in h['metrics'].items():text.append(f"| {h['hour']} | {k} | {s['median_bytes']} | {s['ols_bytes_per_hour']:.3f} | {s['delta_bytes']} |")
text+=['','## Terminal attribution','',f"The original 6.414 MiB is exactly {terminal_delta['/var/log']} bytes between first/last 15-minute medians of the independently identified terminal 76-sample plateau. `/var/log/journal` contributes {terminal_delta['/var/log/journal']} bytes; `/var/log/nginx` contributes {terminal_delta['/var/log/nginx']} bytes. Both contribute; neither alone accounts for the total. `/run/log/journal` contributes zero. Directory scans are sequential, not atomic; residual histogram is retained in measurements.json.",'','## Journal generators','', 'Rendered text bytes approximate serialization cost, not compressed journal disk allocation. Structured systemd unit fields were not archived.','', '| Identifier | Count | Rendered bytes |','| --- | ---: | ---: |']
for k,s in report['journal']['generators'].items():text.append(f"| {k} | {s['count']} | {s['rendered_bytes']} |")
text+=['',report['journal']['rotation_conclusion'],'','Full numeric outputs and request categories: [measurements.json](measurements.json). Raw sample series: [series.csv](series.csv). M8-F remains OPEN; P1 GATED; no qualification credit.']
(out/'README.md').write_text('\n'.join(text)+'\n');print(json.dumps({k:report[k] for k in ['full','terminal','journal','nginx']},indent=2))
