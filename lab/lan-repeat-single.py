#!/usr/bin/env python3
"""Repeat the direct one-client resource gate with the corrected process sampler."""
import json
from pathlib import Path
import subprocess
import sys
import time

root=Path.cwd();q=root/'qualification';source=None
boot=json.loads((q/'final-boot.json').read_text());assert boot['result']=='passed'
try:
    connector=Path('/sys/class/drm/card0-HDMI-A-2/connector_id').read_text().strip()
    assert Path('/sys/class/drm/card0-HDMI-A-2/status').read_text().strip()=='connected'
    subprocess.run(['chvt','3'],check=True)
    argv=['gst-launch-1.0','-q','videotestsrc','is-live=true','pattern=ball','animation-mode=frames',
          '!','video/x-raw,width=1920,height=1080,framerate=30/1','!','videoconvert','!',
          'kmssink','connector-id='+connector,'force-modesetting=true','restore-crtc=true']
    (q/'single-final-source.json').write_text(json.dumps(argv))
    with (q/'single-final-source.log').open('w') as log:
        source=subprocess.Popen(argv,stdout=log,stderr=log)
    time.sleep(3);assert source.poll() is None
    with (q/'single-final.log').open('w') as log:
        r=subprocess.run([sys.executable,str(root/'lab/lan-capacity.py'),'--known-hosts',
             str(Path(boot['run_directory'])/'known_hosts'),'--private-dir',str(root/'private'),
             '--output',str(q/'single-final'),'--clients','1'],stdout=log,stderr=log,timeout=160)
    assert r.returncode==0
    print(json.dumps({'result':'passed'}))
finally:
    if source is not None:source.terminate();source.wait(timeout=10)
    subprocess.run(['chvt','1'],check=False)
