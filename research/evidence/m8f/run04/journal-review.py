import pathlib,json,re,collections,bisect,hashlib
base=pathlib.Path(__file__).parent;root=base/'original/m8f-run04/soak';r=json.loads((root/'result.json').read_text());rows=[json.loads(l) for l in (root/'resources.jsonl').read_text().splitlines()];cycles=r['cycles'];events=r['events'];pattern=re.compile(r'error|fail|timeout|timed out|reset|stall|BUG:|Oops|traceback|out of memory|\bOOM\b|\bWARNING\b|disconnect|suppress|dropped|\bfatal\b|\bcritical\b|segfault|\bhung\b|blocked for|Call Trace:',re.I)
def translate(t):
 z=min(rows,key=lambda z:abs(z['monotonic']-t));return t+z['bridge_monotonic']-z['monotonic']
def in_cycle(t):return any(c['start']<=t<=c['end'] for c in cycles)
def event(t):return next((e['event'] for e in events if e['start']<=t<e['until']),None)
report={'result':'review_pending','journals':{},'clock_mapping':'nearest sampled target/bridge monotonic pair; target wall clock not used','unknown':[]};mapping=[]
for name in ['target-journal-live.log','host-journal-live.log']:
 lines=(root/name).read_text().splitlines();counts=collections.Counter();target=name.startswith('target');scsi=0
 for i,line in enumerate(lines):
  if not pattern.search(line):continue
  m=re.match(r'\[\s*([0-9.]+)\] \S+ (.*)',line)
  if not m:report['unknown'].append([name,i+1,line]);continue
  t=translate(float(m[1])) if target else float(m[1]);msg=m[2];kind=None
  if t<r['start_monotonic']:
   if not target:kind='pre-run host history retained; not qualification failure'
   elif 'Failed to preset all unit:' in msg and ('masked' in msg or 'transient or generated' in msg):kind='known boot preset warning for masked/generated unit'
   elif 'warning is only shown' in msg:kind='known boot BPF firewall capability warning; nftables policy audited separately'
   elif 'suppressing' in msg and 'usrquota' in msg:kind='known unavailable optional tmp usrquota at boot'
   elif 'Received disconnect' in msg or 'Disconnected from user' in msg:kind='normal preflight SSH session closure'
   elif 'Applying preset' in msg or 'factory-reset' in msg or 'Installing SIGUSR2' in msg:kind='benign keyword match in normal startup message'
  elif t>r['end_monotonic']:
   if target and 'HTTP: DEL client' in msg and 'Connection reset by peer' in msg:kind='expected client teardown after controller completed'
   elif target and msg.startswith('sshd-session[') and ('Received disconnect' in msg or 'Disconnected from user' in msg):kind='normal post-run final inventory SSH closure'
   elif not target:kind='post-run host context'
  elif target:
   if msg.startswith('sshd-session[') and ('Received disconnect' in msg or 'Disconnected from user' in msg):kind='normal sampler/workload SSH session closure'
   elif 'Installing SIGUSR2' in msg:kind='normal streamer handler installation after scheduled kvmd restart';assert event(t)=='kvmd'
   elif "Got access denied for user 'invalid-m8d'" in msg:kind='expected auth negative test';assert in_cycle(t)
   elif 'aiohttp.access' in msg and ("'POST /hid/reset HTTP/1.1' => 200" in msg or "'POST /msd/reset HTTP/1.1' => 404" in msg):kind='expected HID/MSD negative/reset API cycle';assert in_cycle(t)
   elif ('connect() to unix:/run/kvmd/api/kvmd.sock failed' in msg or 'Disconnecting clients ...' in msg) and event(t)=='kvmd':kind='scheduled kvmd restart bounded API unavailability'
  else:
   if 'FAILED Result:' in msg:
    stanza=[v for v in lines[i:i+12] if '] user-0 kernel:' in v][:5];assert len(stanza)==5 and 'hostbyte=DID_OK driverbyte=DRIVER_OK' in stanza[0] and 'Sense Key : Not Ready' in stanza[1] and 'Medium not present' in stanza[2] and 'CDB: Read(10)' in stanza[3] and 'I/O error, dev sda' in stanza[4];assert in_cycle(t);kind='expected MSD ejected medium SCSI NOT READY';scsi+=1
   elif 'I/O error, dev sda, sector 0 op 0x0:(READ)' in msg:assert in_cycle(t);kind='expected MSD ejected medium read rejection'
   elif msg.startswith('chronyd[') and 'NTS-KE session' in msg and 'timed out' in msg:kind='known bridge Internet NTS availability; isolated Ethernet workload unaffected'
   elif any(x in msg for x in ['wlo1','p2p-dev-wlo1','FT: Failed to set PTK','nl80211: send_event_marker failed']):kind='known bridge Wi-Fi roaming/control condition; isolated Ethernet workload unaffected'
   elif msg.startswith('sshd-session[') and any(x in msg for x in ['Received disconnect','Disconnected from user','syslogin_perform_logout: logout() returned an error']):kind='bridge administrative SSH closure/accounting warning'
   elif 'systemd-networkd-wait-online' in msg or ('apt-helper[' in msg and 'wait-online returned an error code' in msg):kind='bridge background package network-wait timeout; qualification Ethernet continuity passed'
   elif 'update-notifier-download.service - Download data for packages that failed at package install time' in msg:kind='benign background service description keyword match'
  if kind is None:report['unknown'].append([name,i+1,line]);kind='unexplained'
  counts[kind]+=1;mapping.append({'journal':name,'line':i+1,'classification':kind,'sha256':hashlib.sha256(line.encode()).hexdigest()})
 if not target:assert scsi==len(cycles)==272
 report['journals'][name]={'lines':len(lines),'bytes':(root/name).stat().st_size,'classifications':dict(counts)}
assert not report['unknown'],report['unknown'][:5]
assert report['journals']['target-journal-live.log']['classifications']['expected auth negative test']==272
report['result']='passed';report['unexplained_persistent_failures']=0;report['historical_host_messages_are_not_reclassified_as_passes']=True
(base/'journal-review.json').write_text(json.dumps(report,indent=2)+'\n');(base/'journal-candidate-mapping.json').write_text(json.dumps(mapping,indent=2)+'\n');print(json.dumps(report,indent=2))
