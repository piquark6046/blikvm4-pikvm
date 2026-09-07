#!/usr/bin/env python3
"""Bridge coordinator for direct browser, capacity and optional lifecycle gates."""
import argparse
import json
import os
from pathlib import Path
import pwd
import re
import subprocess
import sys
import time

p=argparse.ArgumentParser();p.add_argument('--boot-result',type=Path,required=True)
p.add_argument('--output',type=Path,required=True);p.add_argument('--private-dir',type=Path,required=True)
p.add_argument('--lifecycle',action='store_true');p.add_argument('--capacity-trials',type=int,default=0)
p.add_argument('--single-resources',action='store_true')
a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
user=pwd.getpwnam('user');os.chown(a.output,user.pw_uid,user.pw_gid)
boot=json.loads(a.boot_result.read_text());assert boot['result']=='passed'
known=str(Path(boot['run_directory'])/'known_hosts')
ssh=['ssh','-i','/home/user/.local/share/blikvm-m7/id_ed25519','-o','BatchMode=yes',
     '-o','StrictHostKeyChecking=yes','-o','UserKnownHostsFile='+known,'blikvm@192.168.88.2']
HERE=Path(__file__).resolve().parent
result={'result':'failed','boot':boot['run_id'],'capacity':[]};source=None;browser=None;off=None

def command(name,argv,input=None):
    r=subprocess.run(argv,input=input,capture_output=True,text=True,timeout=60)
    (a.output/(name+'.log')).write_text(r.stdout+r.stderr)
    assert r.returncode==0,name+': '+r.stderr[-1000:]
    return r.stdout

def inventory(name):
    text=command(name,ssh+['sudo -n python3 -'],(HERE/'lan-inventory.py').read_text())
    value=json.loads(text);assert value['result']=='passed',value.get('error')
    return {'kvmd_pid':value['kvmd_pid'],'streamer_pid':value['ustreamer']['pid'],'boot_id':value['boot_id']}

def start_source(label):
    global source
    f=(a.output/(label+'.log')).open('w')
    argv=['gst-launch-1.0','-q','videotestsrc','is-live=true','pattern=ball','animation-mode=frames',
          '!','video/x-raw,width=1920,height=1080,framerate=30/1','!','videoconvert','!',
          'kmssink','connector-id='+connector,'force-modesetting=true','restore-crtc=true']
    (a.output/(label+'.json')).write_text(json.dumps(argv))
    source=subprocess.Popen(argv,stdout=f,stderr=f)
    time.sleep(3);assert source.poll() is None,'HDMI source failed'

def stop_source():
    global source
    if source is not None:source.terminate();source.wait(timeout=10);source=None

def capacity(label,clients):
    argv=[sys.executable,str(HERE/'lan-capacity.py'),'--known-hosts',known,'--private-dir',str(a.private_dir),
          '--output',str(a.output/label),'--clients',str(clients)]
    with (a.output/(label+'.log')).open('w') as log:
        r=subprocess.run(argv,stdout=log,stderr=log,timeout=160)
    value=json.loads((a.output/label/'result.json').read_text())
    return {'result':value['result'],'path':label,'fps':[x['fps'] for x in value['clients']]}
try:
    result['before']=inventory('inventory-before')
    connector=Path('/sys/class/drm/card0-HDMI-A-2/connector_id').read_text().strip()
    assert Path('/sys/class/drm/card0-HDMI-A-2/status').read_text().strip()=='connected'
    command('vt-source',['chvt','3']);start_source('source')
    env=['env','NODE_EXTRA_CA_CERTS='+str(a.private_dir/'ca.crt'),
         'PLAYWRIGHT_HOST_PLATFORM_OVERRIDE=ubuntu24.04-x64',
         'PLAYWRIGHT_BROWSERS_PATH='+str(Path('out/kvmd-web/browser/browsers').resolve())]
    control=a.output/'control'
    if a.lifecycle:env.append('WEB_LIFECYCLE_DIR='+str(control))
    log=(a.output/'browser.log').open('w')
    browser=subprocess.Popen(['runuser','-u','user','--',*env,'node',str(HERE/'lan-browser.mjs'),
                              str(a.private_dir),str(a.output/'browser'),'120'],stdout=log,stderr=log)
    phases=['nginx-restart','kvmd-restart','hdmi-off','hdmi-on'] if a.lifecycle else []
    deadline=time.monotonic()+480
    done=[]
    while browser.poll() is None:
        assert time.monotonic()<deadline,'browser coordinator timeout'
        for phase in phases:
            if phase in done or not (control/(phase+'-ready')).exists():continue
            if phase in ('nginx-restart','kvmd-restart'):
                service=phase.split('-')[0]
                before=inventory(phase+'-before')
                command(phase,ssh+['sudo -n systemctl restart '+service+' && systemctl is-active '+service])
                time.sleep(3)
                after=inventory(phase+'-after')
                if service=='nginx':assert before['streamer_pid']==after['streamer_pid']
                else:assert before['streamer_pid']!=after['streamer_pid']
            elif phase=='hdmi-off':
                stop_source()
                drm=command('drm-before-off',['modetest','-M','i915','-c'])
                # The retained HIL uses the same libdrm DPMS property discovery.
                prop=re.search(r'\n\s*(\d+) DPMS:',drm.split(connector+'\t',1)[1])
                assert prop,'DPMS property not found'
                offlog=(a.output/'hdmi-off.log').open('w')
                off=subprocess.Popen([sys.executable,str(HERE/'hdmi-off.py'),'--connector',connector,'--property',prop[1]],stdout=offlog,stderr=offlog)
                time.sleep(4);assert off.poll() is None
            else:
                off.terminate();off.wait(timeout=5);off=None;start_source('source-restored')
            (control/(phase+'-done')).write_text('done\n');done.append(phase)
        time.sleep(.25)
    assert browser.returncode==0,'browser failed; see browser/result.json'
    result['browser']=json.loads((a.output/'browser/result.json').read_text())
    assert result['browser']['result']=='passed'
    if a.lifecycle:assert done==phases
    if a.single_resources:
        result['single']=capacity('single-capacity',1)
        assert result['single']['result']=='passed',result['single']
    for i in range(a.capacity_trials):
        result['capacity'].append(capacity('two-capacity-'+str(i+1),2))
    result['after']=inventory('inventory-after')
    result['result']='passed'
except Exception as e:result['error']=str(e)
finally:
    if browser is not None and browser.poll() is None:browser.terminate();browser.wait(timeout=10)
    if off is not None:off.terminate();off.wait(timeout=5)
    stop_source();subprocess.run(['chvt','1'],check=False)
    (a.output/'result.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({'result':result['result'],'capacity':result['capacity'],'error':result.get('error')}))
raise SystemExit(result['result']!='passed')
