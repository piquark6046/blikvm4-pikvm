#!/usr/bin/env python3
"""Verify archived workload and provenance; independently compare Run 03 raw RSS."""
import collections,hashlib,json,pathlib,re,statistics
out=pathlib.Path(__file__).parent; p=pathlib.Path('out/m8f1/review/original/observation01'); q=pathlib.Path('out/m8f0/soak03-review/original')
def read(p):return json.loads(p.read_text())
def lines(p):return [json.loads(s) for s in p.read_text().splitlines()]
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def config(p):
 d={}
 for l in p.read_text().splitlines():
  if l.startswith('CONFIG_'):k,v=l.split('=',1);d[k]=v
  elif l.startswith('# CONFIG_'):d[l.split()[1]]='n'
 return d
manifest=read(p/'frozen-artifacts.json');prod=read(q/'frozen-artifacts.json')
for k,v in manifest['artifacts'].items():assert sha(pathlib.Path('out/m8f1/artifacts')/k)==v['sha256']
c1=config(pathlib.Path('out/m8f0/uvc-candidate-02/artifacts/linux.config'));c2=config(pathlib.Path('out/m8f1/artifacts/linux.config'))
delta={k:{'before':c1.get(k),'after':c2.get(k)} for k in sorted(c1.keys()|c2.keys()) if c1.get(k)!=c2.get(k)}
assert delta==manifest['configuration_delta']
assert all(manifest['artifacts'][k]['sha256']==prod['artifacts'][k]['sha256'] for k in ['initramfs.cpio.gz','sun50i-h616-blikvm-v4.dtb'])
for k in ['initramfs.cpio.gz','sun50i-h616-blikvm-v4.dtb','linux.config']:
 assert sha(pathlib.Path('out/m8f0/uvc-candidate-02/artifacts')/k)==prod['artifacts'][k]['sha256']
before=read(p/'inventory-before.stdout');after=read(p/'inventory-after.stdout');old=read(q/'inventory-before.stdout')
contracts=['kvmd-unit','nginx-unit','auth-config','kvmd-effective','gadget-owner-unit','firewall-config','firewall-unit','blikvm-access-unit']
assert all(before['logs'][k]==after['logs'][k]==old['logs'][k] for k in contracts)
assert before['ustreamer_sha256']==after['ustreamer_sha256']==old['ustreamer_sha256']
workers=['soak-browser.mjs','soak-video.py','hid-api-hil.py','msd-workload.py']
assert all(sha(p/'automation'/k)==sha(q/'automation'/k) for k in workers)
result=read(p/'result.json');assert len(result['cycles'])==139
reads=lines(p/'reads.jsonl');expected='14845cb5d5d773bc3b7411d2e939b948abc9a7fcc04229159f32a355777ec45b'
assert len(reads)==837 and all(x['bytes']==8388608 and x['sha256']==expected for x in reads)
for i in range(139):
 label=f'cycle-{i:04d}';assert read(p/(label+'-hid/result.json'))['result']=='passed'
 assert len([x for x in reads if x['label'].startswith(label)])==6
 for phase in ['before','attached']:
  state=read(p/'msd'/f'{label}-{phase}-api.json');assert state['drive']['connected'] and not state['drive']['rw']
  target=read(p/'msd'/f'{label}-{phase}-target.stdout');assert target['lun']['ro']=='1' and target['hash']==expected
 state=read(p/'msd'/f'{label}-eject-api.json');assert not state['drive']['connected']
 assert 'Medium not present' in read(p/'msd'/f'{label}-eject-tur.log')['stderr']
ui=lines(p/'ui/browser-samples.jsonl');steady=[x for x in ui if not x['planned']]
assert all(x['connected'] and x['width']==1920 and x['height']==1080 and x['api_status']==200 for x in steady)
# Run 03 inputs are independently rehashed; compare only raw time-series fields.
idx=read(q.parent/'soak03-files.json')
for name,f in idx.items():assert sha(q/name)==f['sha256'] and (q/name).stat().st_size==f['bytes']
prodarchive=read(q.parent/'soak03-archive.json');assert sha(q.parent/'soak03-private.tar.gz')==prodarchive['sha256']
rr=lines(q/'resources.jsonl');r0=read(q/'result.json')['start_monotonic'];gens=collections.defaultdict(list)
for x in rr:
 for z in x['processes']:
  if z['comm'].startswith('kvmd/main'):gens[f"{z['comm']}|{z['pid']}|{z['start_ticks']}"].append((x['bridge_monotonic'],z['rss_bytes']/1048576))
def stat(v):return {'n':len(v),'median_MiB':statistics.median(v),'min_MiB':min(v),'max_MiB':max(v)} if v else None
comparison={k:{'start_elapsed_h':(v[0][0]-r0)/3600,'end_elapsed_h':(v[-1][0]-r0)/3600,'first15_median_MiB':statistics.median(x[1] for x in v[:15]),'last15_median_MiB':statistics.median(x[1] for x in v[-15:]),'hourly':[stat([y for t,y in v if r0+h*3600<=t<r0+(h+1)*3600]) for h in range(24)]} for k,v in gens.items()}
sys={m:[stat([int(re.search(r'^'+m+r':\s+(\d+)',x['proc']['meminfo'],re.M)[1])/1024 for x in rr if r0+h*3600<=x['bridge_monotonic']<r0+(h+1)*3600]) for h in range(24)] for m in ['MemAvailable','AnonPages','Shmem','Slab']}
audit=read(pathlib.Path('out/m8f1/runtime-audit.json'))
report={'diagnostic_qualification_seconds':0,'configuration_delta_verified':delta,'artifact_hashes_verified':manifest['artifacts'],'run03_archive_sha256':prodarchive['sha256'],'run03_files_verified':len(idx),'runtime_audit_receipt':{'sha256':sha(pathlib.Path('out/m8f1/runtime-audit.json')),'files':audit['files'],'mismatches':audit['mismatches'],'all_slab_debug_flags_zero':all(v=='0' for v in audit['slab_debug_flags'].values())},'identical_inventory_contracts':contracts,'identical_workload_workers':workers,'cycles_verified':139,'direct_reads_verified':len(reads),'ui_samples':len(ui),'steady_ui_samples':len(steady),'distinct_ui_hashes':len({x['sha256'] for x in ui if 'sha256' in x}),'run03_processes':comparison,'run03_system_hourly':sys}
(out/'context-checks.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if not k.startswith('run03_') and k!='artifact_hashes_verified'},indent=2))
