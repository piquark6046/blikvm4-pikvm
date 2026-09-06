#!/usr/bin/env python3
"""Summarize archived process RSS and service CPU counters without live queries."""
import argparse
import datetime
import json
from pathlib import Path
import re

p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);a=p.parse_args()
hils=[json.loads(line) for line in (a.root/'qualification/hils.jsonl').read_text().splitlines()]
records=[]
for h in hils:
    root=a.root/'runs'/h['run_id']; rss={'kvmd':[],'ustreamer':[]}; samples=[]; stamp=None
    text=(root/'resources.log').read_text()
    for line in text.splitlines():
        if re.fullmatch(r'\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ',line): stamp=datetime.datetime.fromisoformat(line)
        if line.startswith('CPUUsageNSec=') and stamp:
            samples.append((stamp,int(line.split('=')[1])))
    for name in ('resources.log','process-resources-extra.log'):
        if not (root/name).exists(): continue
        for line in (root/name).read_text().splitlines():
            fields=line.split()
            if len(fields)==8 and fields[0].isdigit() and fields[2]=='kvmd':
                rss['kvmd' if fields[1]=='1' else 'ustreamer'].append(int(fields[6]))
    assert all(rss.values()) and len(samples)>2
    elapsed=(samples[-1][0]-samples[0][0]).total_seconds();assert elapsed>0
    records.append({'run_id':h['run_id'],
                    'rss_kib':{k:{'min':min(v),'max':max(v),'samples':len(v)} for k,v in rss.items()},
                    'service_cpu_one_core_percent':(samples[-1][1]-samples[0][1])/1e9/elapsed*100,
                    'cpu_sample_seconds':elapsed})
print(json.dumps({'result':'passed','runs':records,'memory_accounting':'per-process RSS; frozen kernel has no cgroup MemoryCurrent value'},indent=2))
