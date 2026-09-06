#!/usr/bin/env python3
"""Build VM browser/SFTP half of the bounded M8-B qualification."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import time


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--private-dir',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--bridge-known-hosts',type=Path,required=True)
    p.add_argument('--remote-root',default='/home/user/blikvm-web')
    a=p.parse_args()
    private=a.private_dir.resolve();out=a.output.resolve();out.mkdir(exist_ok=False)
    remote=a.remote_root+'/series'
    sftp=['sftp','-b','-','-i',str(private/'bridge_key'),'-o','IdentitiesOnly=yes',
          '-o','StrictHostKeyChecking=yes','-o','UserKnownHostsFile='+str(a.bridge_known_hosts.resolve()),
          'user@172.16.10.118']
    def transfer(batch,required=True):
        proc=subprocess.run(sftp,input=batch,text=True,capture_output=True,timeout=30)
        if required and proc.returncode:
            raise RuntimeError('SFTP transfer failed: '+proc.stderr)
        return proc.returncode==0
    result={'result':'failed','completed':[]}
    tunnel=None
    try:
        for index in range(1,6):
            ready=out/f'ready-{index}.json'
            deadline=time.monotonic()+600
            while not transfer(f'get {remote}/ready-{index}.json {ready}\n',False):
                if time.monotonic()>deadline:raise RuntimeError('bridge ready timeout')
                time.sleep(5)
            value=json.loads(ready.read_text());assert value['index']==index
            transfer(f'get {remote}/known-hosts-{index} {private}/known_hosts\n')
            tunnel_log=(out/f'tunnel-{index}.log').open('w')
            tunnel=subprocess.Popen(['ssh','-F',str(private/'ssh_config'),'-N',
                '-o','ExitOnForwardFailure=yes','-L','127.0.0.1:8443:127.0.0.1:443','target'],
                stdout=tunnel_log,stderr=tunnel_log)
            time.sleep(2)
            assert tunnel.poll() is None,'SSH tunnel failed'
            env=os.environ.copy()
            env['PLAYWRIGHT_HOST_PLATFORM_OVERRIDE']='ubuntu24.04-x64'
            env['PLAYWRIGHT_BROWSERS_PATH']=str(Path('out/kvmd-web/browser/browsers').resolve())
            env.pop('WEB_LIFECYCLE_DIR',None)
            with (out/f'browser-{index}.log').open('w') as log:
                proc=subprocess.run(['node','lab/web-browser.mjs',str(private),
                                     str(out/f'browser-{index}'),'120'],
                                    env=env,stdout=log,stderr=log,timeout=300)
            browser=json.loads((out/f'browser-{index}/result.json').read_text())
            # Publish even a failed browser result so the bridge stops promptly.
            transfer(f'put {out}/browser-{index}/result.json {remote}/browser-{index}.tmp\n'
                     f'rename {remote}/browser-{index}.tmp {remote}/browser-{index}.json\n')
            assert proc.returncode==0 and browser['result']=='passed','browser failed'
            tunnel.terminate();tunnel.wait(timeout=10);tunnel=None;tunnel_log.close()
            result['completed'].append({'index':index,'boot':value['boot']['run_id'],
                                        'fps':browser['stream']['fps']})
            (out/'progress.json').write_text(json.dumps(result,indent=2))
            print(json.dumps(result['completed'][-1]),flush=True)
        result['result']='passed'
    except Exception as error:
        result['error']=str(error)
    finally:
        if tunnel is not None:tunnel.terminate();tunnel.wait(timeout=10)
        (out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    return result['result']=='passed'


if __name__=='__main__':
    raise SystemExit(0 if main() else 1)
