#!/usr/bin/env python3
"""One fresh H3 Chromium preflight. No reboot, reflash or target repair.

Each invocation requires independent replay of its predecessor. Any failure
latches H3 failed, retains outputs, and blocks all later iterations and P3-A.
"""
import argparse
import json
import os
from pathlib import Path
import runpy
import shutil
import subprocess
import sys
import time

H=runpy.run_path(str(Path(__file__).with_name('p3-h3-boundary.py')))
BASE,LEGACY=H['BASE'],H['LEGACY'];require,publish,read=H['require'],H['publish'],H['read_json']
CTX=BASE/'input/context';PREP=BASE/'controller/preparation'


def collect(label,run):
    p=subprocess.run([sys.executable,str(PREP/'collect.py'),str(run/label)],capture_output=True,text=True,timeout=300)
    publish(run/(label+'-transport.json'),{'returncode':p.returncode,'stdout':p.stdout,'stderr':p.stderr})
    require(p.returncode==0,'inventory transport failed')
    inv=read(run/label/'target.json')
    runpy.run_path(str(PREP/'assess.py'))['assess'](inv,read(PREP/'p2-identity.json'))
    original=read(LEGACY/'blikvm-p3/a01/startup/target.json')
    for k in ('boot_id','sd_cid','machine_id','host_public_keys','hash_checks'):
        require(inv[k]==original[k],'target continuity failed: '+k)
    def gen(r):return [line for key in ('services','ssh_show') for line in r['commands'][key]['stdout'].splitlines()
                      if line.startswith(('Id=','InvocationID=','ExecMainStartTimestampMonotonic=','NRestarts='))]
    require(gen(inv)==gen(original),'target generation changed')
    return inv


def protected(config):
    result={}
    for root in [CTX,BASE/'input/nssdb',LEGACY,*map(Path,config['protected_roots'])]:
        # Export archives are immutable but new independent snapshots are allowed.
        if root==Path('/home/user/blikvm-p3-h3-exports'):continue
        result.update(H['manifest'](root,legacy=(root not in (CTX,BASE/'input/nssdb'))))
    return result


def main():
    p=argparse.ArgumentParser();p.add_argument('iteration',type=int,choices=[1,2,3]);a=p.parse_args()
    require(os.geteuid()==0,'root required');os.umask(0o077);H['browser_idle']()
    require(not (BASE/'controller/FAILED.json').exists(),'H3 failed; no retry')
    require(read(BASE/'controller/permission-vm-replay.json')['result']=='H3_PERMISSION_ONLY_PASS','permission replay missing')
    for i in range(1,a.iteration):
        require(read(BASE/'controller'/f'chromium-preflight-{i:03d}-vm-replay.json')['result']=='H3_CHROMIUM_PREFLIGHT_PASS','prior replay missing')
    name=f'chromium-preflight-{a.iteration:03d}';run=BASE/'controller'/name;run.mkdir(mode=0o700)
    config=read(BASE/'controller/config.json')
    config['protected_roots'].append('/home/user/blikvm-p3-h3-exports')
    config['cross_run'] += [str(q) for q in sorted((BASE/'sealed').iterdir())]
    r={'scope':'P3-H3','name':name,'qualification_credit':0,'accepted_cycles':0,'reboots':0,
       'result':'in_progress','stages':[],'started_ns':time.time_ns()}
    publish(run/'start.json',r)
    leaf=None
    try:
        H['browser_idle']();require(not list((BASE/'active').iterdir()),'extra active leaf')
        leaf=BASE/'active'/name;leaf.mkdir(mode=0o700);os.chown(leaf,995,983)
        # Required cross-run mutation attempts precede any target contact.
        H['audit'](leaf,run/'before-target-audit.json',config)
        before=protected(config);publish(run/'protected-before.json',before)
        first=collect('before',run)
        publish(run/'boot-result.json',{'run_directory':'/home/user/blikvm-p2/attempt02/coldboot01',
                    'boot_id':first['boot_id'],'qualification_pass':False})
        for label in ('msd','hid'):
            output=leaf/label;output.mkdir(mode=0o700);os.chown(output,995,983)
            home=output/'runtime-home';(home/'.pki').mkdir(parents=True,mode=0o700)
            shutil.copytree(BASE/'input/nssdb',home/'.pki/nssdb')
            tmp=output/'runtime-tmp';tmp.mkdir(mode=0o700)
            for q in [home,*home.rglob('*'),tmp]:
                os.chown(q,995,983);q.chmod(0o700 if q.is_dir() else 0o600)
            control=run/label;control.mkdir(mode=0o700)
            ack=BASE/'input/acks'/(name+'-'+label);ack.mkdir(mode=0o755);ack.chmod(0o755)
            config['reads'].append(str(BASE/'input/canary'))
            # Root-owned live acknowledgments are separate from fixed inputs;
            # the browser can only read them. They are controller protocol output.
            audit=H['audit'](leaf,run/(label+'-before-audit.json'),config)
            requirements=ack/'launch-requirements.json';publish(requirements,audit['requirements'],0o644)
            require(protected(config)==before,'protected inputs changed before launch')
            env=dict(os.environ,P3_BROWSER_LEAF=str(output),P3_CONTROL=str(ack),
                P3_LAUNCH_REQUIREMENTS=str(requirements),HOME=str(home),TMPDIR=str(tmp),PYTHONDONTWRITEBYTECODE='1')
            with (control/'harness.log').open('x') as log:
                proc=subprocess.run([sys.executable,'lab/'+label+'-browser-hil.py','--output',str(control),
                      '--boot-result',str(run/'boot-result.json')],cwd=CTX,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=850,umask=0o022)
            H['browser_idle']()
            functional=read(control/'result.json');browser=read(output/'browser-result.json')
            gates=[]
            for q in sorted(output.glob('launch-audit-*.json')):
                gate=read(q)
                require((gate['uid'],gate['gid'],gate['groups'])==(995,983,[983]),'launch uid drift')
                require(gate['writable_leaves']==[str(leaf)] and all(o['passed'] for o in gate['operations']),'launch boundary failed')
                publish(control/q.name,gate);gates.append(q.name)
            require(len(gates)==(2 if label=='msd' else 1),'missing launch gate')
            r['stages'].append({'name':label,'returncode':proc.returncode,'result':functional['result'],'launch_gates':gates})
            require(proc.returncode==0 and functional['result']==browser['result']=='passed',label+' functional smoke failed')
            require(protected(config)==before,'protected inputs changed')
        last=collect('after',run)
        publish(run/'protected-after.json',protected(config));require(protected(config)==before,'protected input drift')
        r['seal']=H['seal'](leaf);leaf=None
        config['cross_run'].append(str(BASE/'sealed'/name))
        H['audit'](None,run/'after-seal-audit.json',config)
        r.update(result='COMPLETED_PENDING_INDEPENDENT_REPLAY',target_hashes_matched=10690,
                 boot_id=last['boot_id'],browser_processes=H['browser_idle']())
    except BaseException as e:
        r.update(result='FAILED',error=repr(e));publish(BASE/'controller/FAILED.json',r)
        # Preserve failure without retry, target repair, or rewriting history.
        try:
            H['browser_idle']()
            if leaf is not None and leaf.exists():
                r['failure_seal']=H['seal'](leaf)
            collect('failure-preservation',run)
        except BaseException as more:r['preservation_error']=repr(more)
        raise
    finally:
        r['finished_ns']=time.time_ns();publish(run/'result.json',r)
    print(json.dumps(r),flush=True)


if __name__=='__main__':main()
