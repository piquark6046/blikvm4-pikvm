#!/usr/bin/env python3
"""Descriptive M8-F1 memory accounting; never auto-accepts a run from slopes."""
import argparse
import collections
import json
from pathlib import Path
import re
import statistics as st


def stats(points):
    if not points:
        return None
    ts, vs = zip(*points)
    window = min(5, max(1, len(vs)//4))
    tm, vm = st.mean(ts), st.mean(vs)
    denominator = sum((t-tm)**2 for t in ts)
    return {'samples': len(vs), 'first': vs[0], 'last': vs[-1],
            'first_time': ts[0], 'last_time': ts[-1],
            'min': min(vs), 'max': max(vs), 'median': st.median(vs),
            'absolute_delta': vs[-1]-vs[0],
            'beginning_median': st.median(vs[:window]),
            'final_median': st.median(vs[-window:]),
            'median_delta': st.median(vs[-window:])-st.median(vs[:window]),
            'slope_units_per_hour': sum((t-tm)*(v-vm) for t,v in points)/denominator*3600 if denominator else None}


def analyze(root):
    result = json.loads((root/'result.json' if (root/'result.json').exists() else root/'progress.json').read_text())
    rows = [json.loads(l) for l in (root/'resources.jsonl').read_text().splitlines()]
    start = result['start_monotonic']
    release = result['events'][0]['start'] if result['events'] else None
    series = collections.defaultdict(list)
    aliases = collections.defaultdict(set)
    for s in rows:
        t = s['bridge_monotonic']
        for p in s['processes']:
            key = f"{p['pid']}:{p['start_ticks']}"
            aliases[key].add(p['comm'])
            for k,v in p.get('memory', {}).items():
                series['process/'+key+'/'+k].append((t,v))
            series['process/'+key+'/fds'].append((t,p['fds']))
        for line in s['proc']['meminfo'].splitlines():
            k,v = line.split(':',1); fields=v.split()
            series['meminfo/'+k+('_bytes' if fields[-1]=='kB' else '')].append((t,int(fields[0])*(1024 if fields[-1]=='kB' else 1)))
        for k in ('process_count','socket_count','completed_cycles','sampling_seconds'):
            if k in s: series[k].append((t,s[k]))
        for k,v in zip(('allocated','unused','limit'), s['proc']['sys/fs/file-nr'].split()):
            series['file_nr/'+k].append((t,int(v)))
        for k,v in s['runtime_usage'].items():
            for field,n in v.items():
                if n is not None: series['runtime'+k+'/'+field].append((t,n))
        for p in s.get('other_processes', []):
            series[f"other/{p['comm']}:{p['pid']}:{p['start_ticks']}/rss_bytes"].append((t,p['rss_bytes']))
        for line in (s['proc'].get('vmstat') or '').splitlines():
            k,v=line.split(); series['vmstat/'+k].append((t,int(v)))
        for line in (s['proc'].get('slabinfo') or '').splitlines():
            if line.startswith('#') or line.startswith('slabinfo'): continue
            v=line.split()
            if len(v)>5:
                for k,i in [('active_objects',1),('objects',2),('object_size',3)]:
                    series['slab/'+v[0]+'/'+k].append((t,int(v[i])))
                series['slab/'+v[0]+'/object_capacity_bytes'].append((t,int(v[2])*int(v[3])))
        for k,v in s['ethernet'].items(): series['ethernet/'+k].append((t,v))
        for line in s['proc']['net/sockstat'].splitlines():
            v=line.split()
            for k,n in zip(v[1::2],v[2::2]): series['sockstat/'+v[0]+k].append((t,int(n)))
        clients=s['streamer'].get('result',{}).get('stream',{}).get('clients')
        if clients is not None: series['video_clients'].append((t,clients))
    periods={'first_hour':(start,start+3600),'warmup_hours_1_to_3':(start+3600,start+10800),
             'middle_hours_3_to_8':(start+10800,start+28800),
             'final_four_hours':(start+28800,start+43200),
             'final_two_hours':(start+36000,start+43200)}
    report={}
    for k,points in sorted(series.items()):
        hourly=collections.defaultdict(list)
        for t,v in points: hourly[int((t-start)//3600)].append((t,v))
        report[k]={'all':stats(points),'hourly':{h:stats(v) for h,v in sorted(hourly.items())},
                   'periods':{name:stats([(t,v) for t,v in points if a<=t<b and (release is None or t<release)]) for name,(a,b) in periods.items()}}
    main_keys=[k for k,names in aliases.items() if any(n.startswith('kvmd/main') for n in names)]
    release_review={}
    if release is not None:
        stable=result['events'][0]['until']
        for k in ['meminfo/MemAvailable_bytes','meminfo/AnonPages_bytes','meminfo/Slab_bytes','meminfo/SReclaimable_bytes','meminfo/SUnreclaim_bytes','meminfo/Cached_bytes','meminfo/Shmem_bytes','process_count','socket_count','file_nr/allocated']:
            pts=series[k]; before=stats([(t,v) for t,v in pts if release-300<=t<release]); after=stats([(t,v) for t,v in pts if stable<=t<stable+300])
            release_review[k]={'before':before,'stable_after':after,'after_minus_before':after['median']-before['median'] if before and after else None}
        for field in ('RssAnon_bytes','Private_Dirty_bytes','Private_Clean_bytes','Anonymous_bytes','Pss_bytes','fds'):
            pts=sorted(p for key in main_keys for p in series['process/'+key+'/'+field])
            before=stats([(t,v) for t,v in pts if release-300<=t<release]);after=stats([(t,v) for t,v in pts if stable<=t<stable+300])
            release_review['main/'+field]={'before':before,'stable_after':after,'after_minus_before':after['median']-before['median'] if before and after else None}
    logins=[]
    for line in (root/'target-journal-live.log').read_text().splitlines():
        m=re.search(r'^\[\s*([\d.]+)\].*kvmd\[(\d+)\].*sessions_now=(\d+)',line)
        if m: logins.append(dict(zip(('target_monotonic','pid','sessions_now'),(float(m[1]),int(m[2]),int(m[3])))))
    correlations=[]
    for s in rows:
        auth=[x for x in logins if x['target_monotonic']<=s['monotonic']]
        correlations.append({'bridge_monotonic':s['bridge_monotonic'],'target_monotonic':s['monotonic'],'completed_hid_msd_cycles':s.get('completed_cycles'),'cumulative_logins':len(auth),'last_login':auth[-1] if auth else None,'clients':s['streamer'].get('result',{}).get('stream',{}).get('clients')})
    return {'schema':1,'diagnostic':'M8-F1','decision':'independent_review_required','m8f':'OPEN','production_userspace_changed':False,'diagnostic_kernel':True,'series':report,'aliases':{k:sorted(v) for k,v in aliases.items()},'release':release_review,'correlations':correlations,'method':{'units':'bytes except named counters and sampling_seconds; slab object capacity excludes allocator overhead','windows':'hourly bins anchored to observation start; explicit counts retain partial bins; period endpoints fixed before analysis','slopes':'descriptive only; no automatic boundedness or leak conclusion','accounting':'RSS mappings overlap; Cached includes Shmem and Slab includes SReclaimable/SUnreclaim; do not add overlapping categories','qualification':'diagnostic kernel differs from Run 03; supplemental interpretation requires independent review'}}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
    a.output.write_text(json.dumps(analyze(a.root),indent=2)+'\n')
