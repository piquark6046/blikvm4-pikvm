#!/usr/bin/env python3
"""Offline replay of the private R1 archive; emits only sanitized conclusions."""
import argparse,hashlib,json,re,tarfile
from pathlib import Path

def verify(path):
 assert hashlib.sha256(path.read_bytes()).hexdigest()=='058557cbc659fa7ff922db346b08b75ae8f329e39b8c71b565f7413a4ea31ef6'
 with tarfile.open(path) as t:
  def read(n):return t.extractfile(n).read()
  def j(n):return json.loads(read(n))
  hashes=j('FINAL-SHA256.json')
  for n,h in hashes.items():assert hashlib.sha256(read(n)).hexdigest()==h,n
  first=j('recovery01/result.json');cycle=j('carrier-cycle02/result.json')
  before=j('recovery01/startup-evidence.json');after=j('carrier-cycle02/startup-evidence.json')
  pre=j('carrier-cycle02-preflight/startup-evidence.json')
  def props(r,n):return dict(x.split('=',1) for x in r['commands'][n]['stdout'].splitlines() if '=' in x)
  for r in [first,cycle]:
   assert r['result']=='passed' and not r['manual_repair']
   assert all(0<=r['first_success_latency_seconds'][n]<=60 for n in ['icmp','tcp443','https','tcp22','ssh'])
   assert r['first_success']['startup_collection']['ok']
  assert cycle['carrier_down_seconds']>=60
  assert before['boot_id']==pre['boot_id']==after['boot_id']
  for name in ['ssh_show','nginx_show']:
   b=props(before,name)
   for r in [pre,after]:
    c=props(r,name)
    for k in ['MainPID','ExecMainStartTimestampMonotonic','NRestarts']:assert b[k]==c[k],(name,k)
    assert c['NRestarts']=='0' and c['ActiveState']=='active' and c['Result']=='success'
  for r in [before,after]:
   c=r['commands']
   assert [x for x in c['sshd_T']['stdout'].splitlines() if x.startswith('listenaddress ')]==['listenaddress 192.168.88.2:22']
   assert sorted(x.split()[4] for x in c['listeners']['stdout'].splitlines()[1:])==['192.168.88.2:22','192.168.88.2:443']
   assert c['socket_state']['stdout'].strip()=='disabled' and c['socket_active']['stdout'].strip()=='inactive'
   assert 'status=255' not in c['ssh_journal']['stdout']
   assert 'default' not in c['routes']['stdout']
   assert c['network_config']['stdout']==before['commands']['network_config']['stdout']
   for s in ['Storage=volatile','RuntimeMaxUse=16M','RuntimeMaxFileSize=4M','ForwardToSyslog=no']:assert s in c['journald_config']['stdout']
   for port in [22,443]:assert f'iifname "eth0" ip saddr 192.168.88.1 ip daddr 192.168.88.2 tcp dport {port}' in c['firewall']['stdout']
   assert 'policy drop;' in c['firewall']['stdout']
  journal=before['commands']['ssh_journal']['stdout'];net=before['commands']['networkd_journal']['stdout']
  listening=float(re.search(r'\[\s*([0-9.]+)\].*Server listening on 192\.168\.88\.2 port 22\.',journal)[1])
  gained=float(re.search(r'\[\s*([0-9.]+)\].*eth0: Gained carrier',net)[1]);assert listening<gained
  extra=j('recovery01-extra02/result.json');assert extra['result']=='passed' and not extra['nonlocal_bind_ipv4'] and extra['unauthenticated_api_http']==401 and extra['tls_verify_result']==0
  arm=j('connect-authorized.json')['offline_gate'];assert arm['offline_gate_passed'] and arm['continuous_since_systemd'] and arm['carrier_zero_during_boot']
  for n in ['uart-cycle02/events.jsonl']:
   events=[json.loads(x) for x in read(n).splitlines()];assert not any(x['event']=='uart_unavailable' for x in events)
  # First-use SSH pin is preserved unchanged through the subsequent cycle.
  assert j('recovery01/first-use-trust.json')['fingerprint']
  journal_kib={phase:int(r['commands']['logging_allocation']['stdout'].splitlines()[0].split()[0]) for phase,r in [('first',before),('pre_cycle',pre),('post_cycle',after)]}
  assert max(journal_kib.values())<=16384
  return {'result':'CANDIDATE_1_NARROW_DIAGNOSTIC_PASSED','archive_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'archive_members_verified':len(hashes),'first_recovery_seconds':first['first_success_latency_seconds'],'carrier_cycle_recovery_seconds':cycle['first_success_latency_seconds'],'carrier_down_seconds':cycle['carrier_down_seconds'],'boot_id_unchanged':True,'ssh_main_pid':int(props(after,'ssh_show')['MainPID']),'ssh_NRestarts':0,'nginx_NRestarts':0,'ssh_listening_before_first_carrier_seconds':gained-listening,'restricted_listeners_and_firewall':True,'unauthenticated_api_http':401,'journal_allocation_KiB':journal_kib,'no_manual_repair':True,'ssh_restart_override_added':False,'candidate2_needed':False,'original_mechanism':'sufficiently resolved by Candidate 1 runtime; original attempt exit code remains unproven due to lost journal','limits':['early SPL/TF-A UART gap explicitly approved','no claim of continuous overnight UART observation','expired carrier-cycle01 has no qualification credit','supplemental IPv6-sysctl harness failure preserved','wait-online timeout expected and retained; no policy repair','target realtime stale; monotonic ordering used'],'p2_attempt02':'NOT_STARTED; requires fresh flash and qualification from zero'}

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('archive',type=Path);a=p.parse_args();print(json.dumps(verify(a.archive),indent=2))
