#!/usr/bin/env python3
"""Bridge half of the bounded five-boot M8-B qualification.

The VM supplies browser results through authenticated SFTP. No service repair
is performed after boot. A failed phase stops the series and retains evidence.
"""
import argparse
import json
import os
from pathlib import Path
import pwd
import shutil
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--root', type=Path, required=True)
    a = p.parse_args()
    root = a.root.resolve()
    preflight = json.loads((root/'qualification/preflight-pass.json').read_text())
    assert preflight['result'] == 'passed'
    manifest = json.loads((root/'artifacts/manifest.json').read_text())
    assert preflight['image_sha256'] == manifest['artifacts']['initramfs.cpio.gz']['sha256']
    series = root/'series'
    series.mkdir(exist_ok=False)
    account=pwd.getpwnam('user')
    os.chown(series,account.pw_uid,account.pw_gid)
    source = None
    boots = []
    result = {'result':'failed', 'completed':[]}

    def run(name, command):
        with (series/(name+'.stderr')).open('w') as error:
            proc = subprocess.run(command, stdout=subprocess.PIPE, stderr=error, text=True)
        (series/(name+'.json')).write_text(proc.stdout)
        if proc.returncode:
            raise RuntimeError(name+' failed')
        value = json.loads(proc.stdout)
        assert value['result'] == 'passed', name
        return value

    def inventory(name, bootdir):
        ssh = ['ssh','-i','/home/user/.local/share/blikvm-m7/id_ed25519',
               '-o','BatchMode=yes','-o','StrictHostKeyChecking=yes',
               '-o','UserKnownHostsFile='+str(bootdir/'known_hosts'),
               'blikvm@192.168.88.2','sudo -n python3 -']
        proc = subprocess.run(ssh,input=(HERE/'web-inventory.py').read_text(),
                              text=True,capture_output=True,timeout=60)
        (series/(name+'.json')).write_text(proc.stdout)
        (series/(name+'.stderr')).write_text(proc.stderr)
        assert proc.returncode == 0, name
        assert json.loads(proc.stdout)['result'] == 'passed', name

    try:
        for index in range(1,6):
            boot = run(f'boot-{index}', [sys.executable,str(HERE/'kvmd-boot.py'),
                '--artifacts',str(root/'artifacts'),'--out-root',str(root/'runs'),
                '--require-lab-presets','--boots','1'])
            boots.append(boot)
            (series/'boots.jsonl').write_text(''.join(json.dumps(v)+'\n' for v in boots))
            bootdir = Path(boot['run_directory'])
            run(f'exposure-{index}',[sys.executable,str(HERE/'web-listener-probe.py')])
            inventory(f'startup-{index}',bootdir)
            hil = run(f'hil-{index}', [sys.executable,str(HERE/'web-video-hil.py'),
                '--boot-result',str(series/f'boot-{index}.json'),
                '--out-root',str(root/'runs'),'--seconds','15','--boot-smoke'])
            connector = Path('/sys/class/drm/card0-HDMI-A-2/connector_id').read_text().strip()
            assert Path('/sys/class/drm/card0-HDMI-A-2/status').read_text().strip() == 'connected'
            subprocess.run(['chvt','3'],check=True)
            source_log = (series/f'source-{index}.log').open('w')
            argv = ['gst-launch-1.0','-q','videotestsrc','is-live=true','pattern=ball',
                    'animation-mode=frames','!','video/x-raw,width=1920,height=1080,framerate=30/1',
                    '!','videoconvert','!','kmssink','connector-id='+connector,
                    'force-modesetting=true','restore-crtc=true']
            (series/f'source-{index}.json').write_text(json.dumps(argv))
            source = subprocess.Popen(argv,stdout=source_log,stderr=source_log)
            time.sleep(3)
            assert source.poll() is None, 'moving HDMI source failed'
            shutil.copyfile(bootdir/'known_hosts',series/f'known-hosts-{index}')
            ready = {'index':index,'boot':boot,'hil':hil,'image_sha256':
                     manifest['artifacts']['initramfs.cpio.gz']['sha256']}
            temporary = series/f'ready-{index}.tmp'
            temporary.write_text(json.dumps(ready))
            temporary.rename(series/f'ready-{index}.json')
            deadline = time.monotonic()+600
            ack = series/f'browser-{index}.json'
            while not ack.exists():
                if time.monotonic()>deadline:
                    raise RuntimeError('Build VM browser result timeout')
                if source.poll() is not None:
                    raise RuntimeError('HDMI source terminated')
                time.sleep(1)
            browser = json.loads(ack.read_text())
            assert browser['result']=='passed', 'browser gate failed'
            assert browser['stream']['seconds']>=120 and browser['stream']['fps']>=27
            inventory(f'inventory-{index}',bootdir)
            source.terminate();source.wait(timeout=10);source=None;source_log.close()
            result['completed'].append(index)
            (series/'progress.json').write_text(json.dumps(result))
        run('five-boot-gate',[sys.executable,str(HERE/'ubuntu-reboot-gate.py'),
                             '--series',str(series/'boots.jsonl'),'--runs',str(root/'runs'),'--count','5'])
        result['result']='passed'
    except Exception as error:
        result['error']=str(error)
    finally:
        if source is not None:
            source.terminate();source.wait(timeout=10)
        subprocess.run(['chvt','1'],check=False)
        (series/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))
    return result['result']=='passed'


if __name__=='__main__':
    raise SystemExit(0 if main() else 1)
