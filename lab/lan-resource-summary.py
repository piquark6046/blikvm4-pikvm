#!/usr/bin/env python3
"""Derive CPU/RSS and link counters from archived M8-C samples."""
import argparse
import json
from pathlib import Path


def summarize(path):
    samples=[json.loads(s) for s in path.read_text().splitlines()]
    assert len(samples)>=50
    for sample in samples:
        state=sample['streamer'];assert state['ok']
        state=state['result']
        assert state['encoder']=={'type':'HW','quality':0}
        assert state['source']['resolution']=={'width':1920,'height':1080}
        assert state['source']['online'] and state['source']['desired_fps']==30
    first,last=samples[0],samples[-1];elapsed=last['monotonic']-first['monotonic'];assert elapsed>=115
    delta=[b-a for a,b in zip(first['cpu'],last['cpu'])]
    # Guest ticks are already included in user/nice; exclude them from total.
    total=sum(delta[:8]);busy=total-delta[3]-delta[4]
    processes={}
    for sample in samples:
        for process in sample['processes']:
            processes.setdefault(process['pid'],[]).append((sample['monotonic'],process))
    summary=[]
    for pid,rows in processes.items():
        start,end=rows[0],rows[-1];duration=end[0]-start[0]
        if duration<100:continue
        comm=start[1]['comm']
        summary.append({'pid':pid,'comm':comm,'ppid':start[1]['ppid'],'sample_seconds':duration,
                        'cpu_one_core_percent':(end[1]['ticks']-start[1]['ticks'])/first['hz']/duration*100,
                        'rss_min_kib':min(r[1]['rss_bytes'] for r in rows)//1024,
                        'rss_max_kib':max(r[1]['rss_bytes'] for r in rows)//1024})
    assert any(x['comm'].startswith('kvmd') for x in summary)
    assert sum(x['comm']=='ustreamer' for x in summary)==1
    assert sum(x['comm']=='nginx' for x in summary)==2
    net={k:last['ethernet'][k]-v for k,v in first['ethernet'].items()}
    assert all(net[k]==0 for k in ('rx_errors','tx_errors','rx_dropped','tx_dropped'))
    def tcp(sample):
        lines=sample['snmp'].splitlines()
        i=next(i for i,s in enumerate(lines) if s.startswith('Tcp:'))
        return dict(zip(lines[i].split()[1:],map(int,lines[i+1].split()[1:])))
    before,after=tcp(first),tcp(last)
    return {'sample_seconds':elapsed,'cpu_total_percent':busy/total*100,'processes':summary,
            'ethernet_delta':net,'ethernet_tx_mbps':net['tx_bytes']*8/elapsed/1e6,
            'tcp_delta':{k:after[k]-before[k] for k in ('RetransSegs','InErrs','OutRsts')},
            'streamer_client_states':[s['streamer'].get('result',{}).get('stream',{}) for s in samples]}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('file',type=Path);a=p.parse_args()
    print(json.dumps(summarize(a.file),indent=2))
