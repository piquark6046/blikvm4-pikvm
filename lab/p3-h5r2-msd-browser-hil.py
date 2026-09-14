#!/usr/bin/env python3
"""Real UI actions synchronized with independent target and host storage checks."""
import argparse
import json
import os
from pathlib import Path
import runpy
import subprocess
import time
P3=runpy.run_path(str(Path(__file__).with_name('p3-h2-boundary.py')))
LEAF=Path(os.environ['P3_BROWSER_LEAF'])
PROTOCOL=P3['read_json'](Path(__file__).with_name('p3-h3-protocol.json'))['msd']

M=runpy.run_path(str(Path(__file__).with_name('msd-hil.py')))
p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--boot-result',type=Path,required=True);a=p.parse_args()
h=M['Harness'](a.output,a.boot_result)
result={'result':'failed','stages':[]};source=None;browser=None
try:
    subprocess.run(['chvt','3'],check=True)
    connector=Path('/sys/class/drm/card1-HDMI-A-2/connector_id').read_text().strip()
    source=subprocess.Popen(['gst-launch-1.0','-q','videotestsrc','is-live=true','pattern=ball','animation-mode=frames','!','video/x-raw,width=1920,height=1080,framerate=30/1','!','videoconvert','!','kmssink','connector-id='+connector,'force-modesetting=true','restore-crtc=true'],stdout=(a.output/'source.log').open('w'),stderr=subprocess.STDOUT)
    time.sleep(3);assert source.poll() is None
    browser=subprocess.Popen(['/usr/bin/python3',str(Path(__file__).with_name('p3-h5r2-functional.py')),'browser','msd'],stdout=(a.output/'browser.log').open('w'),stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL,close_fds=True)
    seen=set();deadline=time.monotonic()+360
    while browser.poll() is None:
        assert time.monotonic()<deadline,'browser timeout'
        for stage in sorted(LEAF.glob('[0-9][0-9][0-9].ready')):
            if stage in seen:continue
            seen.add(stage);value=P3['read_json'](stage);P3['require'](stage.name == f'{len(seen):03d}.ready' and value == PROTOCOL[len(seen)-1], 'untrusted MSD stage');check={'result':'failed'}
            try:
                if value.get('reauth'):h.client.login()
                if value['connected']:
                    h.state(value['name'],True);h.media(value['name'])
                else:h.absent(value['name'])
                check['result']='passed'
            except Exception as ex:check['error']=str(ex)
            result['stages'].append({**value,**check})
            P3['publish'](Path(os.environ['P3_CONTROL'])/stage.with_suffix('.ok').name,check,0o644)
        time.sleep(.05)
    result['browser']=P3['read_json'](LEAF/'browser-result.json')
    assert browser.returncode==0,result['browser']
    assert len(seen)==11,len(seen)
    result['result']='passed'
except Exception as ex:result['error']=str(ex)
finally:
    if browser and browser.poll() is None:browser.terminate();browser.wait(timeout=10)
    if source:source.terminate();source.wait(timeout=10)
    subprocess.run(['chvt','1'])
    result['transitions']=h.result['transitions'];h.rec.save_text('result.json',json.dumps(result,indent=2)+'\n')
raise SystemExit(result['result']!='passed')
