#!/usr/bin/env python3
"""Render independently recomputed measurements without making an acceptance decision."""
import json,pathlib,csv
p=pathlib.Path(__file__).parent;r=json.loads((p/'measurements.json').read_text());main=r['processes']['kvmd/main: /usr|889|22446'];lines=['# Independently recomputed tables','','Memory values are MiB; FD, file-nr, process and socket values are counts. Slopes are descriptive MiB/hour (counts/hour for counts). Raw machine-readable values use KiB.','','Each hourly row is the median of all samples in the half-open elapsed-hour interval. First/last medians use the first/last 15 minutes within each selected window; min/max include every sample. Hours 2–4 means elapsed [2,4); the ordinal interpretation [1,4) is also included.','']
def table(headers,rows):
 lines.extend(['| '+' | '.join(headers)+' |','| '+' | '.join(['---']*len(headers))+' |']);lines.extend('| '+' | '.join(str(x) for x in row)+' |' for row in rows);lines.append('')
def fmt(k,v):
 if v is None:return '—'
 if k=='file_limit' and isinstance(v,int):return str(v)
 return f'{v/(1 if k in ["FD","process_count","socket_count","file_allocated","file_unused","file_limit"] else 1024):.3f}'
for keys in ['VmRSS RssAnon RssFile RssShmem Rss Pss Pss_Anon Pss_File Pss_Shmem','Private_Clean Private_Dirty Shared_Clean Shared_Dirty Anonymous Swap FD']:
 ks=keys.split();lines.extend(['## Main kvmd hourly medians','']);table(['Elapsed h','n']+ks,[[f'{i}–{i+1}',v['n']]+[fmt(k,v['metrics'][k]['median']) for k in ks] for i,v in enumerate(main['hourly'])])
for name,v in main['windows'].items():
 lines.extend(['## Main kvmd: '+name,'',f"Samples: {v['n']}; covered elapsed hours {v['first_elapsed_h']:.6f}–{v['last_elapsed_h']:.6f}.",'']);table(['Metric','Median','First 15m','Last 15m','Min','Max','Slope/h'],[[k]+[fmt(k,x[z]) for z in ['median','first_15m_median','last_15m_median','min','max','ols_per_hour']] for k,x in v['metrics'].items() if k!='stat_RSS'])
lines.extend(['## Main kvmd final four hours, 15-minute medians','']);table(['Elapsed h','n','Pss_Anon','Private_Dirty','Anonymous'],[[f'{i/4:.2f}–{(i+1)/4:.2f}',v['n']]+[fmt(k,v['metrics'][k]['median']) for k in ['Pss_Anon','Private_Dirty','Anonymous']] for i,v in enumerate(main['quarter_hour']) if i>=32])
for group,v in r['processes'].items():
 if group.startswith('kvmd/main') or not v['full']:continue
 lines.extend(['## Other service generation: '+group,'']);ks=['Pss','Pss_Anon','Private_Dirty','Anonymous','VmRSS','FD'];table(['Elapsed h','n']+ks,[[f'{i}–{i+1}',h['n']]+[fmt(k,h['metrics'][k]['median']) for k in ks] for i,h in enumerate(v['hourly']) if h])
for ks in [['MemAvailable','MemFree','AnonPages','Cached','Shmem'],['Slab','SReclaimable','SUnreclaim','PageTables','KernelStack'],['process_count','socket_count','file_allocated','file_unused','file_limit']]:
 lines.extend(['## System hourly medians','']);table(['Elapsed h','n']+ks,[[f'{i}–{i+1}',v['n']]+[fmt(k,v['metrics'][k]['median']) for k in ks] for i,v in enumerate(r['system']['hourly'])])
lines.extend(['## System full-generation attribution','']);table(['Metric','First 15m','Last 15m','Change','Min','Max'],[[k,fmt(k,v['first_15m_median']),fmt(k,v['last_15m_median']),fmt(k,v['last_15m_median']-v['first_15m_median']),fmt(k,v['min']),fmt(k,v['max'])] for k,v in r['system']['full']['metrics'].items()])
lines.extend(['## Growing slab classes','', 'Allocated bytes = num_slabs × pagesperslab × 4096, independently parsed from slabinfo. Payload counts are not added to allocated slabs.','']);table(['Class','First 15m','Last 15m','Change MiB'],[[x['class'],fmt('bytes',x['metrics']['allocated']['first_15m_median']),fmt('bytes',x['metrics']['allocated']['last_15m_median']),fmt('bytes',x['delta_KiB'])] for x in r['slab_growth'][:15]])
lines.extend(['## Other long-lived userspace RSS','', 'RSS includes shared file/shmem mappings; these deltas are not added to private memory or Shmem.','']);table(['comm | PID | start_ticks','First 15m','Last 15m','Change MiB'],[[k.replace('|',' / '),fmt('RSS',v['full']['metrics']['RSS']['first_15m_median']),fmt('RSS',v['full']['metrics']['RSS']['last_15m_median']),fmt('RSS',v['full']['metrics']['RSS']['last_15m_median']-v['full']['metrics']['RSS']['first_15m_median'])] for k,v in r['other_processes'].items()])
windows=r['restart_windows'];names=list(windows)
lines.extend(['## Restart window medians','', 'pre10 and pre5 end at the event start. stable_post5 starts at the first two-client sample after the fixed 60-second recovery deadline. final_post5 ends at the last archived sample. all_stable_post covers every such recovered sample.','']);table(['Window','n','First elapsed h','Last elapsed h'],[[n,z['system']['n'],f"{z['system']['first_elapsed_h']:.6f}",f"{z['system']['last_elapsed_h']:.6f}"] for n,z in windows.items()])
keys=['Pss','Pss_Anon','Private_Dirty','Anonymous','VmRSS','RssAnon','FD'];table(['Main kvmd']+names+['stable_post5 − pre5'],[[k]+[fmt(k,next(v for g,v in windows[n]['processes'].items() if g.startswith('kvmd/main'))['metrics'][k]['median']) for n in names]+[fmt(k,next(v for g,v in windows['stable_post5']['processes'].items() if g.startswith('kvmd/main'))['metrics'][k]['median']-next(v for g,v in windows['pre5']['processes'].items() if g.startswith('kvmd/main'))['metrics'][k]['median'])] for k in keys])
ks=list(windows['pre5']['system']['metrics']);table(['System']+names+['stable_post5 − pre5'],[[k]+[fmt(k,windows[n]['system']['metrics'][k]['median']) for n in names]+[fmt(k,windows['stable_post5']['system']['metrics'][k]['median']-windows['pre5']['system']['metrics'][k]['median'])] for k in ks])
for n,z in windows.items():
 lines.extend(['### Restart processes: '+n,'']);table(['Generation','n','Pss','Pss_Anon','Private_Dirty','Anonymous','FD'],[[k.replace('|',' / '),v['n']]+[fmt(m,v['metrics'][m]['median']) for m in ['Pss','Pss_Anon','Private_Dirty','Anonymous','FD']] for k,v in z['processes'].items()])
(p/'tables.md').write_text('\n'.join(lines).rstrip()+'\n')
