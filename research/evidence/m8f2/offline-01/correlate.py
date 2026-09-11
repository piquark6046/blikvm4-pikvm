#!/usr/bin/env python3
"""Supplement sample statistics with independently timestamped workload counts."""
import collections,json,pathlib,re,statistics
p=pathlib.Path('out/m8f1/review/original/observation01');out=pathlib.Path(__file__).parent
rows=[json.loads(l) for l in (p/'resources.jsonl').read_text().splitlines()];result=json.loads((p/'result.json').read_text());t0=result['start_monotonic'];es=[]
for l in (p/'target-journal-live.log').read_text().splitlines(keepends=True):
 m=re.match(r'\[\s*([0-9.]+)\] \S+ ([^:]+): (.*)',l)
 if m and rows[0]['monotonic']<=float(m[1])<=rows[-1]['monotonic']:
  es.append((float(m[1]),re.sub(r'\[\d+\]$','',m[2]),m[3],len(l.encode())))
modules=collections.Counter();module_bytes=collections.Counter()
for t,id,msg,n in es:
 if id=='kvmd':k=msg.split(' --- ')[0];modules[k]+=1;module_bytes[k]+=n
# Convert target monotonic to bridge elapsed using the nearest actual sample.
def elapsed(t):
 r=min(rows,key=lambda r:abs(r['monotonic']-t));return r['bridge_monotonic']-t0+t-r['monotonic']
hourly=[]
for h in range(13):
 selected=[e for e in es if h*3600<=elapsed(e[0])<(h+1)*3600]; rs=[r for r in rows if h*3600<=r['bridge_monotonic']-t0<(h+1)*3600]
 hourly.append({'hour':h,'samples':len(rs),'hid_msd_cycles_started':sum(h*3600<=c['start']-t0<(h+1)*3600 for c in result['cycles']),'messages_by_identifier':dict(collections.Counter(e[1] for e in selected)),'rendered_bytes':sum(e[3] for e in selected)})
# Sampler-specific sudo PID can be identified from COMMAND then matching PAM close/open,
# but the short journal lacks unit/session structured fields. Retain conservative vicinity estimate.
d={'sampling_interval_median_seconds':statistics.median(b['bridge_monotonic']-a['bridge_monotonic'] for a,b in zip(rows,rows[1:])),'kvmd_modules':{k:{'count':v,'rendered_bytes':module_bytes[k]} for k,v in modules.most_common()},'hourly':hourly,'structured_units_available':False,'kernel_and_nginx_messages_in_live_window':sum(e[1] in ['kernel','nginx'] for e in es)}
(out/'correlation.json').write_text(json.dumps(d,indent=2)+'\n')
