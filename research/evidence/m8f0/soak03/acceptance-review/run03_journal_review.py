from run03_resource_review import *
REPLAY=read(ROOT.parent/'independent-replay.json');OLD=read(ROOT.parent/'replay.json')
assert REPLAY==OLD, 'Replay changed'
assert len(REPLAY['checks'])==27 and all(REPLAY['checks'].values())
NAMES=('host-kernel-live.log','target-journal-live.log')
assert sha(ROOT/'host-kernel-live.log')=='49e3b82b7cd21b395caf604eb40fedbf3a65a2166a55d0a91b01bc7a366833e0'
assert sha(ROOT/'target-journal-live.log')=='be9e6bead415fcf3a397f12247d66b90fc0e132009824e91e8075fa2fe34a25f'
LINES={n:(ROOT/n).read_text().splitlines() for n in NAMES}
CAND=re.compile(r'error|fail|timeout|timed out|reset|stall|BUG:|Oops|traceback|out of memory',re.I)
def stamp(l):return float(re.match(r'\[\s*([\d.]+)\]',l)[1])
def corr(n,l):
 t=stamp(l);b=t if n.startswith('host') else bridge(t)
 return {'monotonic_timestamp':t,'clock':'bridge' if n.startswith('host') else 'target','bridge_monotonic_estimate':b,'nearest_scheduled_lifecycle':nearest(b,R['events']),'nearest_hid_msd_exercise':nearest(b,R['cycles'])}
READS=rows(ROOT/'reads.jsonl');CYCLE_EVIDENCE={};HOST_BLOCKS={}
for c in R['cycles']:
 idx=c['index'];label=f'cycle-{idx:04d}';p=ROOT/'msd';hid=read(ROOT/(label+'-hid/result.json'))
 tur=read(p/(label+'-eject-tur.log'));dd=read(p/(label+'-eject-read.log'))
 eject=read(p/(label+'-eject-target.stdout'));attached=read(p/(label+'-attached-target.stdout'))
 rs=[x for x in READS if x['label']==label+'-attached'];assert len(rs)==3
 assert tur['returncode']==2 and 'Medium not present' in tur['stderr'] and dd['returncode']==1
 assert eject['lun']['file']=='' and attached['lun']['file']=='/usr/share/kvmd-msd/images/g4-storage.img'
 assert all(x['sha256']=='14845cb5d5d773bc3b7411d2e939b948abc9a7fcc04229159f32a355777ec45b' and x['bytes']==8388608 and c['start']<x['start']<x['end']<c['end'] for x in rs)
 block=[(i,l) for i,l in enumerate(LINES[NAMES[0]],1) if c['start']<=stamp(l)<=c['end'] and ('[sda]' in l or 'dev sda' in l)]
 assert len(block)==5 and 'FAILED Result: hostbyte=DID_OK driverbyte=DRIVER_OK cmd_age=0s' in block[0][1] and 'Sense Key : Not Ready' in block[1][1] and 'Add. Sense: Medium not present' in block[2][1] and 'CDB: Read(10)' in block[3][1] and 'I/O error, dev sda, sector 0' in block[4][1]
 assert hid['result']=='passed' and len(hid['checks'])==6 and len(hid['authorization'])==4 and len(hid['excluded_routes'])==5
 for i,l in block:HOST_BLOCKS[i]=idx
 CYCLE_EVIDENCE[idx]={'index':idx,'start':c['start'],'end':c['end'],'host_journal_lines':[i for i,l in block],'eject_tur':f'msd/{label}-eject-tur.log','eject_read':f'msd/{label}-eject-read.log','empty_lun':f'msd/{label}-eject-target.stdout','reattached_lun':f'msd/{label}-attached-target.stdout','attached_reads':rs,'seconds_from_expected_read_error_to_last_matching_read':rs[-1]['end']-stamp(block[-1][1]),'hid_auth_and_excluded_route_result':f'{label}-hid/result.json','hid_passed':True}
write('cycle-correlation.json',list(CYCLE_EVIDENCE.values()))
BROWSER=rows(ROOT/'ui/browser-samples.jsonl');EVENTS=[]
for e in R['events']:
 good=[b for b in BROWSER if e['action_end']<=b['t']<=e['until'] and b.get('connected') and b.get('api_status')==200 and b.get('width')==1920 and b.get('height')==1080 and 'sha256' in b]
 assert len({b['sha256'] for b in good})>1
 recovery=next((b for b in good[1:] if b['sha256']!=good[0]['sha256']),None);assert recovery
 ls=[{'line':i,'original_line':l} for i,l in enumerate(LINES[NAMES[1]],1) if e['start']<=bridge(stamp(l))<=e['until'] and any(x in l for x in ('systemctl restart','systemd[','Starting streamer','Capturing ...','NEW client','DEL client','Logged out','Logged in','client socket','new client session','Stopped kvmd/hid','Process killed','Installing SIGUSR'))]
 EVENTS.append({**e,'offset_hours':round((e['start']-START)/3600),'browser_first_good_after_action':good[0],'browser_first_changed_after_action':recovery,'recovered_motion_seconds_after_event_start':recovery['t']-e['start'],'strict_recovery_120_second_fps':next(v for t,v in REPLAY['recovery_120_second_fps'] if abs(t-e['until'])<.001),'mechanism':{'nginx':'Scheduled systemctl restart closes proxy sockets, service stops successfully, starts, accepts two new stream clients.','kvmd':'Scheduled restart runs orderly HID/streamer cleanup with exitcode/retcode 0, removes API socket temporarily, restarts exactly one streamer and three HID workers.','logout':'Explicit UI logout revokes 182 sessions; denied MSD API then successful login restores browser session and motion.','hdmi':'Controller stops source, records DRM DPMS value 3 for signal loss, waits 10 seconds, restores source/DPMS 0. Changed browser hashes and strict recovery window prove moving recovery.'}[e['event']],'target_sequence':ls})
write('lifecycle-correlation.json',EVENTS)
# Full-message coverage: explicit rules, no generic ERROR/unknown-message exemption.
coverage=collections.Counter();unknown=[];candidate_records=[];full_groups=collections.defaultdict(lambda:{'count':0,'line_numbers':[]})
for n in NAMES:
 seen=[]
 for i,l in enumerate(LINES[n],1):
  c=corr(n,l);b=c['bridge_monotonic_estimate'];cy=c['nearest_hid_msd_exercise'];ev=c['nearest_scheduled_lifecycle'];inside=cy['inside_window'];event=ev['inside_window'];proof=[];cl=None
  if n.startswith('host'):
   if i in HOST_BLOCKS:cl='expected MSD eject/reattach consequence';proof=[f'cycle-correlation.json index={HOST_BLOCKS[i]}: five-line sense block, empty LUN, intentional one-sector read, three matching whole-image reads within same cycle']
   elif ' kernel: wlo1: ' in l:
    cl='unrelated bridge-host message';proof=['Wi-Fi roaming/authentication on wlo1; KVM path is dedicated wired eth0/enp1s0 at 192.168.88.0/24. Full stream/API/SSH evidence continues and target eth0 error/drop/carrier counters remain unchanged.']
   elif ' kernel: perf: interrupt took too long (' in l and 'lowering kernel.perf_event_max_sample_rate to ' in l:
    cl='unrelated bridge-host message';proof=['Host perf sampling self-throttles; no target warning, missed evidence coverage or KVM throughput failure.']
  else:
   if 'aiohttp.access' in l:
    m=re.search(r"'(GET|POST) (.*?) HTTP/1.1' => (\d+);",l);assert m,l
    method,path,status=m.groups();status=int(status)
    if status==200:cl='expected successful workload'
    elif status==101 and 'GET /ws ' in l:cl='expected successful workload'
    elif status in (401,403,404) and inside:
     h=read(ROOT/f"cycle-{cy['index']:04d}-hid/result.json")
     allowed401=['/hid/events/send_key','/hid/events/send_mouse_move','/hid/events/send_mouse_relative']
     if status==401 and path.split('?')[0] in allowed401:cl='expected authentication negative test'
     elif status==403 and path=='/auth/login':cl='expected authentication negative test'
     elif status==404 and path in [v['route'] for v in h['excluded_routes']]:cl='expected disabled-route negative test'
    elif status==403 and event and ev['event']=='logout' and path=='/msd':cl='expected authentication negative test';proof=['ui/browser-event.json and logout-denied browser sample; lifecycle-correlation.json logout bounded recovery']
    if path=='/hid/reset' and status==200:
     assert inside;cl='expected HID reset exercise';proof=[f"cycle-{cy['index']:04d}-hid/result.json: six exact evdev checks and cleanup; automation/hid-api-hil.py clear()"]
    if not proof:proof=[f"HTTP {status}; cycle={cy['index'] if inside else None}; archived API/browser results and unchanged replay"]
   elif "Got access denied for user 'invalid-m8d' from auth service 'htpasswd'" in l and inside:
    cl='expected authentication negative test';proof=[f"cycle-{cy['index']:04d}-hid/result.json authorization invalid-credentials=403; subsequent six exact evdev checks passed"]
   elif 'Installing SIGUSR2 streamer handler ...' in l and event and ev['event']=='kvmd':
    cl='known documented benign diagnostic';proof=['False lexical match: inSTALLing contains stall. This installs the normal streamer signal handler; lifecycle-correlation.json records new streamer, exact mode and bounded recovery.']
   elif 'account blikvm has password changed in future' in l:
    cl='known documented benign diagnostic';proof=['RAM target realtime is July 27/28 while image was built in September; 2263 accepted public-key SSH sessions open and close successfully in complete journal. Qualification uses monotonic time. No password-auth failure is inferred from this account-age diagnostic.']
   elif ' kvmd[' in l and ' INFO --- ' in l:
    module=l.split(']: ',1)[1].split(' INFO --- ',1)[0].strip();msg=l.split(' INFO --- ',1)[1]
    if module=='kvmd.apps.kvmd.auth' and msg.startswith(('Authorized user','Logged in user')):cl='expected authentication activity';proof=['All 1098 logged sessions have infinite expiry; retained-session trend is reviewed separately in resource-review.json.']
    elif module=='kvmd.apps.kvmd.auth' and msg.startswith('Logged out user') and event and ev['event']=='logout':cl='expected lifecycle consequence'
    elif event and any(module.startswith(x) for x in ('kvmd.apps.kvmd','kvmd.htserver','kvmd.plugins.hid.otg.device','kvmd.plugins.msd.otg','asyncio.events')):
     cl='expected lifecycle consequence';proof=['Exact lifecycle window AND orderly service stop/start, exitcode=0, new clients and independently replayed bounded recovery; lifecycle-correlation.json.']
    elif b<START and ('NEW client' in msg or 'Registered new client session' in msg):cl='expected startup consequence'
    elif b>=END and 'HTTP: DEL client' in msg:cl='expected cleanup consequence';proof=['Controller stop marker follows result end; client worker exits normally. Not a timed-soak interruption.']
   elif re.search(r' (sshd-session|sudo|runuser)\[\d+\]: ',l):
    msg=l.split(']: ',1)[1]
    if any(x in msg for x in ('Accepted publickey for blikvm','pam_unix(sshd:session): session opened','pam_unix(sshd:session): session closed','pam_unix(sudo:session): session opened','pam_unix(sudo:session): session closed','pam_unix(runuser:session): session opened','pam_unix(runuser:session): session closed','Received disconnect from','Disconnected from user blikvm','PWD=/home/blikvm ; USER=root ; COMMAND=/usr/bin/python3 -','COMMAND=/usr/bin/systemctl restart')):cl='expected SSH/inventory activity'
   elif ' systemd[' in l:
    msg=l.split(']: ',1)[1]
    if any(x in msg for x in ('systemd-tmpfiles-clean.service','motd-news.service','dpkg-db-backup.service','apt-daily-upgrade.service','apt-daily.service')) and any(x in msg for x in ('Starting ','Finished ','Deactivated successfully.','Consumed ')):cl='expected background service activity'
    elif event and any(x in msg for x in ('nginx.service','kvmd.service')) and any(x in msg for x in ('Starting ','Started ','Stopping ','Stopped ','Deactivated successfully.','Consumed ')):cl='expected lifecycle consequence'
   elif event and re.search(r' (nginx|nft)\[\d+\]: ',l):
    cl='expected lifecycle consequence';proof=['nginx configuration test and recorded firewall rules at scheduled restart; completed service start and bounded client recovery.']
  if cl is None:cl='unexplained';unknown.append({'source':n,'line':i,'original_line':l,**c})
  if not proof:proof=['Complete-journal message-family review; see journal-review.json full_coverage and corresponding archived successful workload/lifecycle records.']
  coverage[(n,cl)]+=1
  # Preserve a lossless line-index inventory grouped by class; original journals remain immutable/hash-verified.
  full_groups[(n,cl)]['count']+=1;full_groups[(n,cl)]['line_numbers'].append(i)
  if CAND.search(l):
   seen.append(l);candidate_records.append({'source_journal':n,'line_number':i,'original_line':l,**c,'classification':cl,'supporting_evidence':proof})
 assert seen==OLD['journal_candidates'][n],n
with (OUT/'journal-candidates.jsonl').open('w') as f:
 for v in candidate_records:f.write(json.dumps(v,separators=(',',':'))+'\n')
write('journal-full-coverage.json',[{'source':n,'classification':cl,**v} for (n,cl),v in full_groups.items()])
# Explicit full-journal search, separate from verifier's broad candidate regex.
patterns={'USB resets':r'usb.*\breset\b|reset (?:high|full|low|super)-speed USB','UVC errors':r'uvc.*(?:error|fail|timeout)|(?:error|fail).*uvc','failed URB resubmission':r'(?:resubmit|resubmission).*urb|urb.*(?:resubmit|resubmission|error|fail)','MUSB/UDC timeout or stall':r'(?:musb|udc).*(?:timeout|timed out|stall|error|fail)','SCSI timeout/reset':r'(?:scsi|\bsd \d).*\b(?:timeout|timed out|reset)\b','HID backend/write errors':r'(?:hid|hidg).*(?:ERROR|CRITICAL|write.*(?:fail|error)|timeout)','kvmd traceback':r'Traceback|most recent call last','unexpected service exit':r'Main process exited|Failed with result|Failed to start|status=\d+/(?:FAILURE|ABRT|SEGV)|core.dump|exitcode=[^0]|retcode=[^0]','nginx fatal errors':r'nginx.*(?:emerg|alert|crit|fatal|\[error\])','kernel WARNING/Oops/BUG':r'\bWARNING:|\bOops\b|\bBUG:|kernel panic|Call trace:','OOM':r'out of memory|oom.kill|invoked oom|Killed process \d+','network loss':r'Link is Down|NETDEV WATCHDOG|tx timeout|network is unreachable|No route to host|Connection timed out|wlo1:.*(?:disconnect|deauth)','Run02 malformed JPEG signature':r'invalid JPEG markers|malformed.*JPEG|trailing.*(?:JPEG|EOI)|invalid-frame-'}
search={}
for label,pat in patterns.items():
 hits=[{'source':n,'line':i,'original_line':l} for n in NAMES for i,l in enumerate(LINES[n],1) if re.search(pat,l,re.I)]
 search[label]={'pattern':pat,'count':len(hits),'matches':hits}
# Full supplemental nginx error log: baseline prefix distinguishes historical pre-run errors.
BEFORE=read(ROOT/'inventory-before.stdout')['logs'];AFTER=read(ROOT/'inventory-after.stdout')['logs'];aux={}
for k in ('nginx-error','target-dmesg'):
 old=BEFORE[k];new=AFTER[k];assert new.startswith(old),k
 suffix=new[len(old):];aux[k]={'baseline_lines':len(old.splitlines()),'final_lines':len(new.splitlines()),'baseline_exact_prefix':True,'new_lines':suffix.splitlines(),'before_sha256':hashlib.sha256(old.encode()).hexdigest(),'after_sha256':hashlib.sha256(new.encode()).hexdigest()}
# Nginx uses target realtime; infer target monotonic from sampled realtime, never bridge wall time.
ng=[]
for l in aux['nginx-error']['new_lines']:
 dt=datetime.datetime.strptime(l[:19],'%Y/%m/%d %H:%M:%S').replace(tzinfo=datetime.timezone.utc).timestamp();s=min(S,key=lambda s:abs(s['time']-dt));t=s['monotonic']+dt-s['time'];b=bridge(t);e=nearest(b,R['events'])
 assert e['event']=='kvmd' and e['inside_window'] and 'connect() to unix:/run/kvmd/api/kvmd.sock failed' in l and ('(111: Connection refused)' in l or '(2: No such file or directory)' in l),l
 ng.append({'original_line':l,'target_monotonic_estimate':t,'bridge_monotonic_estimate':b,'classification':'expected lifecycle consequence','supporting_evidence':'kvmd restart removes API listener; controller and video-events record bounded 502s; new kvmd starts and clients recover within original 60-second window.'})
aux['nginx-error']['new_line_reviews']=ng
assert not aux['target-dmesg']['new_lines']
write('journal-review.json',{'result':'passed' if not unknown else 'unexplained','scope':'Every line of the complete archived host kernel follow log and target all-unit follow journal. Host all-unit userspace journal was not captured by original controller and is not claimed. Supplemented by full baseline/final nginx error log and kernel inventory; original file scopes are explicit.','sources':{n:{'sha256':sha(ROOT/n),'lines':len(LINES[n]),'first_monotonic':stamp(LINES[n][0]),'last_monotonic':stamp(LINES[n][-1])} for n in NAMES},'candidate_counts':{n:len(OLD['journal_candidates'][n]) for n in NAMES},'full_coverage':[{'source':n,'classification':cl,'lines':count} for (n,cl),count in coverage.items()],'candidate_classifications':dict(collections.Counter(x['classification'] for x in candidate_records)),'unexplained':unknown,'explicit_searches':search,'supplemental_logs':aux,'strict_video':{'accepted_frames':2583555,'parser_unchanged':sha(ROOT/'automation/stream-client.py')==sha(Path('lab/stream-client.py')),'parser_sha256':sha(ROOT/'automation/stream-client.py'),'malformed_jpeg_events':[],'invalid_frame_files':[p.name for p in ROOT.glob('invalid-frame-*')],'worker_result':read(ROOT/'video-result.json'),'video_events':rows(ROOT/'video-events.jsonl'),'does_not_override_journal_failure':True},'limitations':['One-minute resources cannot bound sub-sample spikes; target-to-bridge timestamp mapping includes unmeasured sample completion latency.','Historical nginx errors predate Run 03 and match baseline byte-for-byte; they are preserved, not reclassified as new Run 03 failures.','No new journal collection or target operation was performed.'],'review_notes':['272 expected host failed READ(10) blocks each contain DID_OK/DRIVER_OK and Medium not present, followed within the same cycle by three full matching direct reads. No USB/SCSI transport error is excused by mere proximity.','False lexical candidates include 816 successful /hid/reset requests, 272 excluded /msd/reset requests and inSTALLing SIGUSR2.','All full-journal message families are accounted for; unexpected meaningful messages default to unexplained.']})
print('journal review',len(candidate_records),'candidates','unknown',len(unknown),'new nginx errors',len(ng))
if unknown:print(json.dumps(unknown[:12],indent=2))
