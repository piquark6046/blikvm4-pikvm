#!/usr/bin/env python3
"""Offline independent raw-proc review; no imports from generated analyzers.
All memory quantities are KiB, slopes KiB/hour; counts remain integers.
"""
import argparse, collections, hashlib, json, pathlib, re, statistics, tarfile
P=argparse.ArgumentParser();P.add_argument('--archive-root',default='out/m8f1/review');P.add_argument('--output',default='research/evidence/m8f1/independent-review-01');a=P.parse_args()
root=pathlib.Path(a.archive_root); src=root/'original/observation01'; out=pathlib.Path(a.output);out.mkdir(parents=True,exist_ok=True)
def digest(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def read(p):return json.loads(p.read_text())
def lines(p):return [json.loads(s) for s in p.read_text().splitlines()]
def fields(s):return {m[0]:int(m[1]) for m in re.findall(r'^([A-Za-z_]+):\s+(\d+) kB$',s,re.M)}
index=read(root/'observation01-files.json'); archive=read(root/'observation01-archive.json')
assert digest(root/'observation01-private.tar.gz')==archive['sha256']
for f in index:
 p=src/f['path'];assert p.stat().st_size==f['bytes'] and digest(p)==f['sha256'],f['path']
# Verify tar members against extracted inputs, not just an index and local copy.
with tarfile.open(root/'observation01-private.tar.gz') as tar:
 members={m.name:m for m in tar.getmembers() if m.isfile()}
 for f in index:
  names=[n for n in members if n.endswith('/observation01/'+f['path']) or n=='observation01/'+f['path']]
  assert len(names)==1,(f['path'],names)
  assert hashlib.sha256(tar.extractfile(members[names[0]]).read()).hexdigest()==f['sha256']
rows=lines(src/'resources.jsonl'); result=read(src/'result.json'); t0=result['start_monotonic'];ev=result['events'][0]; restart=ev['start']
metrics='VmRSS RssAnon RssFile RssShmem Rss Pss Pss_Anon Pss_File Pss_Shmem Private_Clean Private_Dirty Shared_Clean Shared_Dirty Anonymous Swap'.split()
sysmetrics='MemAvailable MemFree AnonPages Cached Shmem Slab SReclaimable SUnreclaim PageTables KernelStack'.split()
groups=collections.defaultdict(list); systems=[]; slabs=collections.defaultdict(list); other=collections.defaultdict(list)
for r in rows:
 t=r['bridge_monotonic'];s={'t':t,**fields(r['proc']['meminfo']), 'process_count':r['process_count'],'socket_count':r['socket_count']}
 s.update(zip(['file_allocated','file_unused','file_limit'],map(int,r['proc']['sys/fs/file-nr'].split())))
 for path,v in r['runtime_usage'].items():
  if v['allocated_bytes'] is not None:s['du:'+path]=v['allocated_bytes']/1024
 s['service_Pss_Anon']=sum(fields(p['raw']['smaps_rollup'])['Pss_Anon'] for p in r['processes'] if p['comm'].startswith('kvmd') or p['comm']=='ustreamer')
 assert r['socket_count']==sum(len(r['proc']['net/'+n].splitlines())-1 for n in ['tcp','udp','unix'])
 systems.append(s)
 for p in r['processes']:
  raw=p['raw'];stat=raw['stat'].rsplit(')',1)[1].split();assert int(stat[19])==p['start_ticks']
  status=raw['status'];assert int(re.search(r'^Pid:\s+(\d+)',status,re.M)[1])==p['pid']
  assert re.search(r'^Name:\s+(.+)',status,re.M)[1]==p['comm'] or (p['comm']=='ustreamer' and re.search(r'^Name:\s+(.+)',status,re.M)[1]=='main') or (p['pid']==39187 and t<ev['until'])
  v={**fields(status),**fields(raw['smaps_rollup'])}; assert all(m in v for m in metrics)
  groups[f"{p['comm']}|{p['pid']}|{p['start_ticks']}"].append({'t':t,**v,'FD':p['fds'],'stat_RSS':p['rss_bytes']/1024})
 for p in r['other_processes']:other[f"{p['comm']}|{p['pid']}|{p['start_ticks']}"].append({'t':t,'RSS':p['rss_bytes']/1024})
 for line in r['proc']['slabinfo'].splitlines()[2:]:
  w=line.split(); i=w.index('slabdata');slabs[w[0]].append({'t':t,'allocated':int(w[i+2])*int(w[5])*4,'active_payload':int(w[1])*int(w[3])/1024})
def select(series,start,end):return [x for x in series if start<=x['t']<end]
def stats(series,keys,edge=900):
 if not series:return None
 ts=[x['t'] for x in series];first=select(series,ts[0],ts[0]+edge);last=select(series,ts[-1]-edge,ts[-1]+.001)
 res={'n':len(series),'first_elapsed_h':(ts[0]-t0)/3600,'last_elapsed_h':(ts[-1]-t0)/3600,'metrics':{}}
 for k in keys:
  vals=[x[k] for x in series];xs=[(t-ts[0])/3600 for t in ts];xm=statistics.mean(xs);ym=statistics.mean(vals);den=sum((x-xm)**2 for x in xs)
  res['metrics'][k]={'median':statistics.median(vals),'first_15m_median':statistics.median(x[k] for x in first),'last_15m_median':statistics.median(x[k] for x in last),'min':min(vals),'max':max(vals),'ols_per_hour':sum((x-xm)*(y-ym) for x,y in zip(xs,vals))/den if den else None}
  if k=='file_limit':
   assert len(set(vals))==1
   for name in ['median','first_15m_median','last_15m_median','min','max']:res['metrics'][k][name]=vals[0]
 return res
windows={'first_hour':(0,1),'hours_2_to_4':(2,4),'ordinal_hours_2_through_4':(1,4),'hours_4_to_8':(4,8),'final_four_hours':(8,12),'final_two_hours':(10,12)}
def summary(series,keys):
 return {'hourly':[stats(select(series,t0+h*3600,t0+(h+1)*3600),keys) for h in range(12)],'windows':{n:stats(select(series,t0+lo*3600,t0+hi*3600),keys) for n,(lo,hi) in windows.items()},'full':stats(select(series,t0,restart),keys),'quarter_hour':[stats(select(series,t0+h*900,t0+(h+1)*900),keys) for h in range(48)]}
main='kvmd/main: /usr|889|22446';new='kvmd/main: /usr|39187|4347364'
pre=[r for r in rows if r['bridge_monotonic']<restart];post=[r for r in rows if r['bridge_monotonic']>=restart]
assert len(rows)==737 and len(result['events'])==1
assert all(any(p['comm']=='kvmd/main: /usr' and p['pid']==889 and p['start_ticks']==22446 for p in r['processes']) for r in pre)
assert all(not r['failed_units']['stdout'].strip() and r['failed_units']['rc']==0 for r in rows)
clients=collections.Counter(str(r.get('streamer',{}).get('result',{}).get('stream',{}).get('clients')) for r in rows)
stable=next(r['bridge_monotonic'] for r in post if r['bridge_monotonic']>=ev['until'] and r['streamer']['result']['stream']['clients']==2)
last=rows[-1]['bridge_monotonic'];rw={'pre10':(restart-600,restart),'pre5':(restart-300,restart),'stable_post5':(stable,stable+300),'final_post5':(last-300,last+.001),'all_stable_post':(stable,last+.001)}
release={n:{'system':stats(select(systems,lo,hi),sysmetrics+['service_Pss_Anon','process_count','socket_count','file_allocated']),'processes':{k:stats(select(v,lo,hi),metrics+['FD']) for k,v in groups.items() if select(v,lo,hi)}} for n,(lo,hi) in rw.items()}
slab_growth=[]
for k,v in slabs.items():
 z=stats(select(v,t0,restart),['allocated','active_payload']);delta=z['metrics']['allocated']['last_15m_median']-z['metrics']['allocated']['first_15m_median'];slab_growth.append({'class':k,'delta_KiB':delta,**z})
slab_growth.sort(key=lambda x:x['delta_KiB'],reverse=True)
report={'units':'KiB; slopes KiB/hour; FD/file/process/socket counts unscaled','source_archive':archive,'integrity':{'files_rehashed':len(index),'tar_members_matched':len(index),'resources_sha256':digest(src/'resources.jsonl')},'scope':{'samples':len(rows),'pre_restart_samples':len(pre),'post_restart_samples':len(post),'last_main_sample_elapsed_seconds':pre[-1]['bridge_monotonic']-t0,'restart_elapsed_seconds':restart-t0,'post_restart_sample_span_seconds':last-post[0]['bridge_monotonic'],'stable_post_sample_span_seconds':last-stable,'clients_histogram':dict(clients),'failed_unit_samples':0,'boot_ids':sorted({r['boot_id'] for r in rows}),'qualification_seconds':0,'events':result['events'],'sampling_seconds':stats([{'t':r['bridge_monotonic'],'seconds':r['sampling_seconds']} for r in rows],['seconds'])},'processes':{k:summary(v,metrics+['FD','stat_RSS']) for k,v in groups.items()},'system':summary(systems,sysmetrics+['service_Pss_Anon','process_count','socket_count','file_allocated','file_unused','file_limit']+[k for k in systems[0] if k.startswith('du:')]),'other_processes':{k:summary(v,['RSS']) for k,v in other.items() if len(v)>600 and max(x['RSS'] for x in v)>0},'slab_growth':slab_growth,'restart_windows':release}
for k,v in report['processes'].items():
 if k!=main:v.pop('quarter_hour')
for v in report['other_processes'].values():v.pop('quarter_hour')
report['terminal_constant']={}
for metric in ['Pss_Anon','Private_Dirty','Anonymous']:
 v=groups[main];i=len(v)-1
 while i>0 and v[i-1][metric]==v[-1][metric]:i-=1
 report['terminal_constant'][metric]={'start_elapsed_h':(v[i]['t']-t0)/3600,'samples':len(v)-i,'minutes':(v[-1]['t']-v[i]['t'])/60,'value_KiB':v[-1][metric]}
report['terminal_75_minutes_system']=stats(select(systems,groups[main][-76]['t'],restart),sysmetrics+['service_Pss_Anon','process_count','socket_count']+[k for k in systems[0] if k.startswith('du:')])
(out/'measurements.json').write_text(json.dumps(report,indent=2)+'\n')
# Small chart source: one point per actual sample, separate panels, no overlapping sums.
import csv
with (out/'series.csv').open('w') as f:
 w=csv.writer(f,lineterminator="\n");w.writerow(['elapsed_h','main_Pss_Anon_KiB','main_Private_Dirty_KiB','main_Anonymous_KiB','MemAvailable_KiB','AnonPages_KiB','Shmem_KiB','Slab_KiB'])
 for s in systems:
  p=next((x for k in [main,new] for x in groups[k] if x['t']==s['t']),None)
  w.writerow([(s['t']-t0)/3600,*([p[m] for m in ['Pss_Anon','Private_Dirty','Anonymous']] if p else ['']*3),*[s[m] for m in ['MemAvailable','AnonPages','Shmem','Slab']]])
print(json.dumps(report['scope'],indent=2))
for h,z in enumerate(report['processes'][main]['hourly']):print(h,{k:round(z['metrics'][k]['median']/1024,3) for k in ['Pss','Pss_Anon','Private_Dirty','Anonymous','VmRSS']})
