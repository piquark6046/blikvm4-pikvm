import json,pathlib,re,statistics,collections,hashlib
base=pathlib.Path(__file__).parent;root=base/'original/m8f-run04/soak';r=json.loads((root/'result.json').read_text());rows=[json.loads(l) for l in (root/'resources.jsonl').read_text().splitlines()];start=r['start_monotonic'];out=base/'resources';out.mkdir(exist_ok=True)
raw={}
for p in list(root.glob('sample-*.stdout'))+[root/n for n in ['baseline.stdout','final.stdout','kvmd-restart-before.stdout','kvmd-restart-after.stdout']]:
 z=json.loads(p.read_text());raw[z['monotonic']]=z
for z in rows:assert raw[z['monotonic']]=={k:v for k,v in z.items() if k not in ['bridge_monotonic','planned']}
series=[];removed=[];previous={}
for z in rows:
 q={'hours':(z['bridge_monotonic']-start)/3600,'planned':z['planned']};mem=z['proc']['meminfo']
 for k in ['MemAvailable','MemFree','Shmem','AnonPages','Cached','Slab','SReclaimable','SUnreclaim']:q[k]=int(re.search(r'^'+k+r':\s+(\d+)',mem,re.M)[1])/1024
 for k,v in z['logging']['directories'].items():q[k]=v['allocated_bytes']/1048576
 q['journal_MiB']=sum(f['allocated_bytes'] for f in z['logging']['files'])/1048576
 for k in ['process_count','socket_count']:q[k]=z[k]
 q['file_nr_allocated']=int(z['proc']['sys/fs/file-nr'].split()[0]);q['main_RSS_MiB']=sum(p['rss_bytes'] for p in z['processes'] if p['comm'].startswith('kvmd/main'))/1048576
 current={(f['path'].split('/')[1],f['inode']):f for f in z['logging']['files']}
 for k,f in previous.items():
  if k not in current:removed.append({'hours':q['hours'],'inode':k[1],'path':f['path']})
 previous=current;series.append(q)
def stats(points,k):
 xs=[q['hours'] for q in points];ys=[q[k] for q in points];xm=statistics.mean(xs);ym=statistics.mean(ys);den=sum((x-xm)**2 for x in xs)
 return {'n':len(ys),'first':ys[0],'last':ys[-1],'min':min(ys),'max':max(ys),'median':statistics.median(ys),'first15_median':statistics.median(ys[:15]),'last15_median':statistics.median(ys[-15:]),'slope_per_hour':sum((x-xm)*(y-ym) for x,y in zip(xs,ys))/den if den else None}
phases={}
for name,a,b in [('first2',0,2),('middle',2,20),('final4',20,24.1),('final2',22,24.1)]+[(f'hour{i}',i,i+1) for i in range(24)]:
 ps=[q for q in series if a<=q['hours']<b];phases[name]={k:stats(ps,k) for k in ps[0] if k not in ['hours','planned']}
audit={}
for side in ['before','after']:
 p=json.loads((root/f'logging-policy-{side}.stdout').read_text());assert p['result']=='passed' and not p['regular_log_writers'];audit[side]={'result':p['result'],'journald_sha256':hashlib.sha256(p['journald'].encode()).hexdigest(),'nginx_sha256':hashlib.sha256(p['nginx'].encode()).hexdigest()}
report={'samples':len(rows),'raw_samples_verified':len(rows),'phases':phases,'automatic_journal_file_removals':removed,'policy':audit,'journal_max_MiB':max(q['journal_MiB'] for q in series),'all_journald_healthy':all(z['logging']['health']['rc']==0 for z in rows),'all_disk_usage_successful':all(z['logging']['disk_usage']['rc']==0 for z in rows),'nginx_files_empty':all(all(v['size']==0 for v in z['logging']['nginx_logs'].values()) for z in rows),'decision':'review_pending'}
(out/'review.json').write_text(json.dumps(report,indent=2)+'\n');(out/'series.json').write_text(json.dumps(series)+'\n')
print(json.dumps({k:v for k,v in report.items() if k not in ['phases','automatic_journal_file_removals']},indent=2));print('removals',len(removed))
for phase in ['first2','middle','final4','final2']:
 print(phase,json.dumps({k:phases[phase][k] for k in ['MemAvailable','Shmem','main_RSS_MiB','journal_MiB']}))
