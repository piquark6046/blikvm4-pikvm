import bisect, collections, datetime, hashlib, json, math, re, statistics as st
from pathlib import Path
ROOT=Path('out/m8f0/soak03-review/original')
OUT=Path('research/evidence/m8f0/soak03/acceptance-review');OUT.mkdir(exist_ok=True)
def read(p):return json.loads(p.read_text())
def rows(p):return [json.loads(l) for l in p.read_text().splitlines()]
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def write(n,o): (OUT/n).write_text(json.dumps(o,indent=2)+'\n')
assert sha(ROOT/'resources.jsonl')=='e52a76d0676e9bf77044e4c113f03919c292cb66e54d1b049ca2e3d693c8ad45', 'Review is pinned to immutable Run 03'
assert sha(ROOT/'result.json')=='3f2d8b6b20fde939f186e8dae13c510a946fff37c2f848dbf5b1f6b5feda28ab'
R=read(ROOT/'result.json');S=rows(ROOT/'resources.jsonl');START=R['start_monotonic'];END=R['end_monotonic']
T=[s['monotonic'] for s in S];B=[s['bridge_monotonic'] for s in S]
def bridge(t):
 i=max(0,min(len(T)-2,bisect.bisect_right(T,t)-1));f=(t-T[i])/(T[i+1]-T[i]);return B[i]+f*(B[i+1]-B[i])
def utc(t):return datetime.datetime.fromtimestamp(R['start_utc']+t-START,datetime.timezone.utc).isoformat()
def nearest(t,items):
 x=min(items,key=lambda x:abs(t-x['start']));return {**x,'seconds_from_start':t-x['start'],'inside_window':x['start']<=t<=x.get('until',x.get('end'))}
def basic(points):
 if not points:return None
 ts,vs=zip(*points);n=len(vs);w=min(15,max(1,n//4));mid=(ts[0]+ts[-1])/2
 mean=st.mean(ts);vmean=st.mean(vs);den=sum((t-mean)**2 for t in ts)
 def stats(a):
  if not a:return None
  tt,vv=zip(*a);ww=min(15,max(1,len(vv)//4));tm=st.mean(tt);vm=st.mean(vv);dd=sum((t-tm)**2 for t in tt);return {'beginning_median':st.median(vv[:ww]),'final_median':st.median(vv[-ww:]),'median_delta':st.median(vv[-ww:])-st.median(vv[:ww]),'least_squares_units_per_hour':sum((t-tm)*(v-vm) for t,v in a)/dd*3600 if dd else None,'samples':len(vv),'min':min(vv),'max':max(vv),'median':st.median(vv),'first':vv[0],'last':vv[-1],'endpoint_delta':vv[-1]-vv[0]}
 tail=[(t,v) for t,v in points if t>=ts[-1]-21600] if ts[-1]-ts[0]>=21600 else []
 lastchange=next((ts[i] for i in range(n-1,0,-1) if vs[i]!=vs[i-1]),ts[0]);hours=collections.defaultdict(list)
 for t,v in points:hours[int((t-START)//3600)].append((t,v))
 return {'samples':n,'first':vs[0],'last':vs[-1],'min':min(vs),'max':max(vs),'median_window_samples':w,'beginning_median':st.median(vs[:w]),'final_median':st.median(vs[-w:]),'median_delta':st.median(vs[-w:])-st.median(vs[:w]),'endpoint_delta':vs[-1]-vs[0],'nondecreasing':all(b>=a for a,b in zip(vs,vs[1:])),'strictly_increasing':n>1 and all(b>a for a,b in zip(vs,vs[1:])),'increases':sum(b>a for a,b in zip(vs,vs[1:])),'decreases':sum(b<a for a,b in zip(vs,vs[1:])),'least_squares_units_per_hour':sum((t-mean)*(v-vmean) for t,v in points)/den*3600 if den else None,'first_half':stats([(t,v) for t,v in points if t<=mid]),'second_half':stats([(t,v) for t,v in points if t>mid]),'final_six_hours':stats(tail),'constant_tail_seconds':ts[-1]-lastchange,'last_change_bridge_monotonic':lastchange,'hourly':[{ 'run_hour':h,**stats(v)} for h,v in hours.items()]}
# Full journal login stream; no tokens are emitted.
LOG=(ROOT/'target-journal-live.log').read_text().splitlines();AUTH=[]
for i,l in enumerate(LOG,1):
 m=re.search(r'sessions_now=(\d+)',l)
 if m:
  t=float(re.match(r'\[\s*([\d.]+)',l)[1]);AUTH.append({'line':i,'target_monotonic':t,'bridge_monotonic_estimate':bridge(t),'sessions_now':int(m[1]),'pid':int(re.search(r'kvmd\[(\d+)\]',l)[1]),'infinite_expiry':'expire=INF' in l})
G=collections.defaultdict(list)
for s in S:
 for p in s['processes']:G[(p['comm'],p['pid'],p['start_ticks'])].append((s,p))
GENERATIONS=[]
for key,g in G.items():
 first,last=g[0][0],g[-1][0];a=first['bridge_monotonic'];b=last['bridge_monotonic'];rss=basic([(s['bridge_monotonic'],p['rss_bytes']) for s,p in g]);fds=basic([(s['bridge_monotonic'],p['fds']) for s,p in g])
 auth=[v for v in AUTH if a<=v['bridge_monotonic_estimate']<=b];cycles=[c['index'] for c in R['cycles'] if c['end']>=a and c['start']<=b]
 note='RSS is constant throughout the sampled generation.'
 if rss['min']!=rss['max']:note='RSS changes; constant-tail duration and every hourly bin are reported. A flat tail is observational evidence, not an allocation bound.'
 if key[0]=='kvmd':note='Single startup sample; comm changes to kvmd/main: /usr with identical PID/start_ticks. This is not an extra restart. Kept separate by exact requested identity.'
 if key[0].startswith('kvmd/main'):note+=' Main kvmd growth remains mechanistically unattributed; early flat periods also precede later sustained growth. Auth session retention is a confounder, not a demonstrated explanation of all RSS.'
 GENERATIONS.append({'identity':dict(zip(('comm','pid','start_ticks'),key)),'first_sample':{'bridge_monotonic':a,'target_monotonic':first['monotonic'],'bridge_utc':utc(a)},'last_sample':{'bridge_monotonic':b,'target_monotonic':last['monotonic'],'bridge_utc':utc(b)},'lifetime_covered_seconds':b-a,'sample_count':len(g),'rss_bytes':rss,'fds':fds,'cycles_overlapping':[min(cycles),max(cycles)] if cycles else [],'logins_in_coverage':len(auth),'session_first_last':[auth[0]['sessions_now'],auth[-1]['sessions_now']] if auth else None,'lifecycle_events_in_coverage':[e for e in R['events'] if a<=e['start']<=b],'client_counts':dict(collections.Counter(str(s['streamer'].get('result',{}).get('stream',{}).get('clients','unavailable')) for s,p in g)),'constant_tail_observed':rss['constant_tail_seconds']>0,'plateau_assessment':('not assessable from one startup sample' if len(g)==1 else 'no sustained terminal plateau; final hourly medians still rise before restart' if key[0].startswith('kvmd/main') and key[1]==3689 else 'late observed plateau for 3.405 hours; boundedness not established' if key[0].startswith('kvmd/main') else 'constant throughout coverage' if rss['min']==rss['max'] else 'stable after final step; exact constant-tail coverage reported'),'review':note})
SYSTEM=collections.defaultdict(list);NET=collections.defaultdict(list)
for s in S:
 t=s['bridge_monotonic']
 for line in s['proc']['meminfo'].splitlines():
  k,v=line.split(':',1)
  if k in ('MemAvailable','MemFree','Cached','Slab','SReclaimable','SUnreclaim','Shmem','AnonPages','Mapped','PageTables','KernelStack','Buffers','SwapFree','Dirty','Writeback'):SYSTEM[k+'_bytes'].append((t,int(v.split()[0])*1024))
 for k in ('process_count','socket_count'):SYSTEM[k].append((t,s[k]))
 for k,v in zip(('file_nr_allocated','file_nr_unused','file_nr_limit'),map(int,s['proc']['sys/fs/file-nr'].split())):SYSTEM[k].append((t,v))
 for line in s['proc']['net/sockstat'].splitlines():
  v=line.split()
  for k,x in zip(v[1::2],v[2::2]):SYSTEM['sockstat_'+v[0][:-1]+'_'+k].append((t,int(x)))
 for name in ('net/snmp','net/netstat'):
  ls=s['proc'][name].splitlines()
  for a,b in zip(ls[::2],ls[1::2]):
   a=a.split();b=b.split()
   for k,v in zip(a[1:],b[1:]):NET[a[0][:-1]+'.'+k].append((t,int(v)))
 for k,v in s['ethernet'].items():NET['eth0.'+k].append((t,v))
# Each resource sample carries cycle/event/auth/client correlations; every generation remains separate.
with (OUT/'resource-correlations.jsonl').open('w') as f:
 for i,s in enumerate(S):
  t=s['bridge_monotonic'];last=START if i==0 else S[i-1]['bridge_monotonic'];auth=[v for v in AUTH if last<v['bridge_monotonic_estimate']<=t]
  f.write(json.dumps({'sample_index':i,'bridge_monotonic':t,'target_monotonic':s['monotonic'],'planned':s['planned'],'nearest_cycle':nearest(t,R['cycles']),'nearest_lifecycle':nearest(t,R['events']),'logins_since_previous_sample':len(auth),'last_login':next((v for v in reversed(AUTH) if v['bridge_monotonic_estimate']<=t),None),'video_clients':s['streamer'].get('result',{}).get('stream',{}).get('clients'),'generations':[{k:p[k] for k in ('comm','pid','start_ticks','rss_bytes','fds')} for p in s['processes']]},separators=(',',':'))+'\n')
write('resource-review.json',{'schema':1,'result':'inconclusive','source':{'resources_sha256':sha(ROOT/'resources.jsonl'),'existing_verifier_sha256':sha(ROOT.parent/'replay.json'),'sample_count':len(S)},'method':{'identity':['comm','pid','start_ticks'],'samples':'all 1441, including scheduled windows; original verifier excluded 5 planned samples','medians':'Same beginning/final count as verifier: min(15,max(1,n//4)); hourly bins anchored to run start; include partial bins explicitly by sample count. Halves split covered time, not sample index. All sizes bytes. No new MiB acceptance threshold.','clock':'Bridge receipt times paired with target monotonic per sample. Linear interpolation for target journal correlation; receipt latency is unmeasured, so bridge mappings are estimates, not exact synchronization. Mechanisms are also checked in same-clock target sequences and raw host cycle windows.','rss':'RSS includes shared mappings; do not sum child RSS as private physical memory. SReclaimable is part of Slab; Cached equals Shmem here and is not evidence of freely reclaimable disk cache.'},'generations':GENERATIONS,'system':{k:basic(v) for k,v in SYSTEM.items()},'network':{k:basic(v) for k,v in NET.items()},'authentication':{'logins':len(AUTH),'all_expire_infinite':all(x['infinite_expiry'] for x in AUTH),'last_sessions':AUTH[-1]['sessions_now'],'login_records':AUTH,'logout':[{'line':i,'original_line':l} for i,l in enumerate(LOG,1) if 'Logged out user' in l]},'review':{'boundedness_established':False,'continuing_leak_demonstrated':False,'fd_process_socket_accumulation':False,'memory_attribution':'RSS plateau observed, but no heap/PSS/allocator evidence attributes delayed growth. MemAvailable loss co-occurs with AnonPages and RAM-backed Cached=Shmem growth; journal-file allocation/rotation and filesystem sizes were not measured. Do not assert that all Shmem growth is bounded journal retention.','required_next_step':'Targeted memory diagnostic, proposed only; no target action and no new full soak.'}})
if __name__=='__main__':print('resource review generated',len(GENERATIONS),'identities')
