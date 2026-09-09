#!/usr/bin/env python3
"""Bridge-only bounded M8-F0 runner; frozen target, no lifecycle changes."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import runpy
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--known-hosts', type=Path, required=True)
    p.add_argument('--private-dir', type=Path, required=True)
    p.add_argument('--seconds', type=int, default=900)
    p.add_argument('--stop-file', type=Path)
    a = p.parse_args()
    os.umask(0o077)
    a.output.mkdir(exist_ok=False)
    automation = a.output/'automation'
    automation.mkdir()
    manifest = {}
    for name in ('mjpeg-observe.py', 'mjpeg-observe-run.py', 'mjpeg-observe-compare.py', 'soak-resources.py'):
        data = (HERE/name).read_bytes()
        (automation/name).write_bytes(data)
        manifest[name] = hashlib.sha256(data).hexdigest()
    (a.output/'automation.json').write_text(json.dumps(manifest,indent=2)+'\n')
    ssh = ['ssh','-i','/home/user/.local/share/blikvm-m7/id_ed25519', '-o','BatchMode=yes',
           '-o','StrictHostKeyChecking=yes','-o','UserKnownHostsFile='+str(a.known_hosts),
           '-o','ConnectTimeout=10','-o','ServerAliveInterval=10','-o','ServerAliveCountMax=2',
           'blikvm@192.168.88.2']
    client = runpy.run_path(str(HERE/'hid-api-hil.py'))['Client'](a.private_dir)
    source = None
    secret = a.private_dir/f'm8f0-{os.getpid()}.conf'
    def snapshot(name):
        r = subprocess.run(ssh+['sudo -n python3 -'],input=(HERE/'soak-resources.py').read_bytes(),capture_output=True,timeout=30)
        (a.output/(name+'.json')).write_bytes(r.stdout)
        (a.output/(name+'.stderr')).write_bytes(r.stderr)
        if r.returncode:
            raise RuntimeError('runtime snapshot failed')
    try:
        client.login()
        token = next(c.value for c in client.cookies if c.name == 'auth_token')
        secret.write_text('cookie = "auth_token='+token+'"\n')
        connector = (Path('/sys/class/drm/card0-HDMI-A-2/connector_id')).read_text().strip()
        subprocess.run(['chvt','3'],check=True)
        subprocess.run(['modetest','-M','i915','-w',connector+':DPMS:0'],check=True,stdout=subprocess.DEVNULL)
        with (a.output/'source.log').open('wb') as log:
            source = subprocess.Popen(['gst-launch-1.0','-q','videotestsrc','is-live=true','pattern=ball',
              'animation-mode=frames','!','video/x-raw,width=1920,height=1080,framerate=30/1','!',
              'videoconvert','!','kmssink','connector-id='+connector,'force-modesetting=true','restore-crtc=true'],stdout=log,stderr=log)
        time.sleep(3)
        if source.poll() is not None:
            raise RuntimeError('moving HDMI source failed')
        snapshot('before')
        # Context is sampled immediately after each anomaly. Existing read-only
        # sampler records PID/start time, negotiated mode and boot identity.
        sampler = 'sudo -n python3 -c '+__import__('shlex').quote((HERE/'soak-resources.py').read_text())
        config = {'context_command':ssh+[sampler], 'sources':{
          'direct':{'path':'unix:/run/kvmd/ustreamer/ustreamer.sock:/stream',
            'command':ssh+['sudo -n curl --http1.0 -fsS -N -i --unix-socket /run/kvmd/ustreamer/ustreamer.sock "http://localhost/stream?extra_headers=1"']},
          'https':{'path':'https://blikvm-v4.lab/streamer/stream',
            'command':['curl','--config',str(secret),'--cacert',str(a.private_dir/'ca.crt'),
              '--interface','192.168.88.1','--http1.1','-fsS','-N','-i',
              'https://blikvm-v4.lab/streamer/stream?extra_headers=1']}}}
        config_path = a.output/'config.json'
        config_path.write_text(json.dumps(config,indent=2)+'\n')
        subprocess.run([sys.executable,str(HERE/'mjpeg-observe.py'),'--config',str(config_path),
          '--output',str(a.output/'clients'),'--seconds',str(a.seconds)]+
          (['--stop-file',str(a.stop_file.resolve())] if a.stop_file else []),check=True)
        snapshot('after')
        results = {name:json.loads((a.output/'clients'/name/'result.json').read_text())
                   for name in ('direct','https')}
        complete = all(r['result'] == 'observation_complete' for r in results.values()) and source.poll() is None
        (a.output/'runner-result.json').write_text(json.dumps({'result':
          'observation_complete' if complete else 'observation_incomplete',
          'qualification':'NOT_RUN','source_alive':source.poll() is None,
          'clients':results},indent=2)+'\n')
    finally:
        if source:
            source.terminate()
            try: source.wait(timeout=10)
            except subprocess.TimeoutExpired: source.kill();source.wait()
        secret.unlink(missing_ok=True)
        try: client.request('/auth/logout',{})
        except Exception: pass


if __name__ == '__main__':
    main()
