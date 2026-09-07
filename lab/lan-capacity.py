#!/usr/bin/env python3
"""Independent authenticated direct HTTPS clients with unchanged 120s/27fps gates."""
import argparse
import hashlib
import http.cookiejar
import json
import os
from pathlib import Path
import ssl
import subprocess
import sys
import time
import urllib.parse
import urllib.request

p=argparse.ArgumentParser();p.add_argument('--known-hosts',required=True)
p.add_argument('--private-dir',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
p.add_argument('--clients',type=int,choices=(1,2),required=True);p.add_argument('--seconds',type=int,default=120)
a=p.parse_args();assert a.seconds>=120
a.output.mkdir(exist_ok=False,parents=True)
ssh=['ssh','-i','/home/user/.local/share/blikvm-m7/id_ed25519','-o','BatchMode=yes',
     '-o','StrictHostKeyChecking=yes','-o','UserKnownHostsFile='+a.known_hosts,'blikvm@192.168.88.2']
base='https://blikvm-v4.lab';credentials=json.loads((a.private_dir/'credentials.json').read_text())
ctx=ssl.create_default_context(cafile=str(a.private_dir/'ca.crt'))
result={'result':'failed','clients':[],'seconds':a.seconds,'target_fps':27,'client_count':a.clients,
        'path':'192.168.88.1 enp1s0 -> 192.168.88.2 eth0 TCP/443; no tunnel'}
result['automation_sha256']={}
for name in ('lan-capacity.py','lan-resources.py','stream-client.py'):
    data=Path(__file__).with_name(name).read_bytes()
    (a.output/('source-'+name)).write_bytes(data)
    result['automation_sha256'][name]=hashlib.sha256(data).hexdigest()
processes=[];cookies=[];openers=[];commands=[];sampler=None
try:
    for i in range(a.clients):
        jar=http.cookiejar.CookieJar()
        opener=urllib.request.build_opener(urllib.request.HTTPSHandler(context=ctx),urllib.request.HTTPCookieProcessor(jar))
        with opener.open(base+'/api/auth/login',urllib.parse.urlencode(credentials).encode(),timeout=10) as r:assert r.status==200
        cookie=next(c.value for c in jar if c.name=='auth_token')
        config=a.private_dir/f'capacity-{os.getpid()}-{i}.conf'
        fd=os.open(config,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
        with os.fdopen(fd,'w') as f:f.write('cookie = "auth_token='+cookie+'"\n')
        cookies.append(config);openers.append(opener)
    resource_log=(a.output/'target-resources.jsonl').open('w')
    sampler=subprocess.Popen(ssh+['sudo -n python3 - '+str(a.seconds+4)],stdin=subprocess.PIPE,stdout=resource_log,stderr=(a.output/'resources.stderr').open('w'),text=True)
    sampler.stdin.write((a.output/'source-lan-resources.py').read_text());sampler.stdin.close()
    start=time.time()
    for i,config in enumerate(cookies):
        argv=[sys.executable,str(Path(__file__).with_name('stream-client.py')),'--seconds',str(a.seconds),
              '--out',str(a.output/f'client-{i}'),'--','curl','--config',str(config),'--cacert',str(a.private_dir/'ca.crt'),
              '--interface','192.168.88.1','--http1.1','-sS','--no-buffer','--include','--max-time',str(a.seconds+10),base+'/streamer/stream']
        log=(a.output/f'client-{i}.log').open('w')
        commands.append(argv)
        processes.append(subprocess.Popen(argv,stdout=log,stderr=log))
    result['measurement_processes']=[proc.pid for proc in processes]
    assert len(set(result['measurement_processes']))==a.clients
    for proc in processes:proc.wait(timeout=a.seconds+20)
    for i in range(a.clients):
        root=a.output/f'client-{i}';r=json.loads((root/'result.json').read_text())
        frames=[json.loads(line) for line in (root/'frames.jsonl').read_text().splitlines()]
        stamps=[0]+[f['t'] for f in frames]+[a.seconds]
        gap=max(b-c for c,b in zip(stamps,stamps[1:]))
        r.update(fps=r['frames']/r['elapsed'],max_gap=gap,measurement_start_unix=start)
        r['capacity_passed']=(r['result']=='passed' and r['frames']>=a.seconds*27 and r['fps']>=27 and gap<=3)
        result['clients'].append(r)
    sampler.wait(timeout=15);resource_log.close();assert sampler.returncode==0
    # Each independent authenticated session reconnects after its bounded stream closes.
    result['reconnect']=[]
    for i,opener in enumerate(openers):
        with opener.open(base+'/streamer/state',timeout=10) as r:assert r.status==200
        with opener.open(base+'/streamer/snapshot',timeout=10) as r:
            frame=r.read();assert r.status==200 and len(frame)>4 and frame[:2]==b'\xff\xd8'
        argv=commands[i].copy()
        argv[argv.index('--seconds')+1]='5'
        argv[argv.index('--out')+1]=str(a.output/f'reconnect-{i}')
        with (a.output/f'reconnect-{i}.log').open('w') as log:
            proc=subprocess.run(argv,stdout=log,stderr=log,timeout=15)
        reconnect=json.loads((a.output/f'reconnect-{i}/result.json').read_text())
        assert proc.returncode==0 and reconnect['result']=='passed'
        result['reconnect'].append({'client':i,'authenticated_state':True,'snapshot_bytes':len(frame),
                                    'frames':reconnect['frames'],'unique_hashes':reconnect['unique_hashes'],
                                    'stream_result':reconnect['result']})
    result['result']='passed' if all(r['capacity_passed'] for r in result['clients']) else 'failed'
except Exception as e:result['error']=str(e)
finally:
    for proc in processes:
        if proc.poll() is None:proc.terminate();proc.wait(timeout=5)
    if sampler is not None and sampler.poll() is None:sampler.terminate();sampler.wait(timeout=5)
    for opener in openers:
        try:opener.open(urllib.request.Request(base+'/api/auth/logout',data=b'',method='POST'),timeout=5).close()
        except Exception:pass
    for config in cookies:config.unlink(missing_ok=True)
    (a.output/'result.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({'result':result['result'],'fps':[r['fps'] for r in result['clients']],'error':result.get('error')}))
raise SystemExit(result['result']!='passed')
