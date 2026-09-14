#!/usr/bin/env python3
"""Conditional H5R1 functional preflights; no reboot, reflash or service repair."""
import json
import os
from pathlib import Path
import runpy
import shutil
import subprocess
import sys
import time
import uuid

BASE=Path('/var/lib/blikvm-p3-h5r1')
P=runpy.run_path(str(BASE/'input/p3-h5r1.py'))
H=P['H'];require,publish,read=P['require'],P['publish'],P['read']
CTX=BASE/'input/functional';PREP=BASE/'controller/functional-preparation'
HERE=Path(__file__).resolve().parent


def source_check():
    s=read(HERE/'functional-source-provenance.json')
    require(s['clean'] and s['commit']==s['origin_main'],'functional source not pushed clean')
    for name,digest in s['files'].items():
        require(Path(name).name==name and H['digest'](HERE/name)==digest,'functional source drift')
    return s


def prerequisites():
    require(not (BASE/'controller/FAILED.json').exists(),'H5R1 FAILED; no retry')
    for i in range(1,4):P['prior_replay'](f'minimal-{i:03d}')
    require(read(BASE/'controller/minimal-comparison.json')['result']=='THREE_MINIMAL_CONTRACTS_MATCH','minimal comparison missing')


def prepare():
    source=source_check();prerequisites();P['idle']()
    require(P['manifest'](BASE/'input')==read(BASE/'controller/input-manifest.json'),'minimal input drift')
    require(not CTX.exists(),'functional input already prepared')
    old=Path('/var/lib/blikvm-p3-h3/input/context')
    pins={'msd-browser-hil.py':'5817c9daaf52d5e41e02bc05561301cef2fb8d654cd70f5b61bd883e94e02e7d',
          'hid-browser-hil.py':'2728f880e9b2eb0f94078d76f402552680b4af7f2495c581b0f440fcabe227f8',
          'msd-browser.mjs':'739aa5ea1d7bf84432a9676ada1251267f6637a0c3358ae61cf5f4093a1e48ae',
          'hid-browser.mjs':'6265c640c23ff02116ad0ccc5b47f1a5b5ca13308df8c6c5f3d95a14272b6576'}
    for name,digest in pins.items():require(H['digest'](old/'lab'/name)==digest,'frozen functional reference drift')
    P['mkdir'](CTX,0o755)
    for name in ('lab','build','initramfs'):
        shutil.copytree(old/name,CTX/name,symlinks=True)
    P['mkdir'](CTX/'private',0o750)
    c=read(BASE/'input/contract.json')
    for name in ('ca.crt','credentials.json','server.crt'):
        shutil.copyfile(old/'private'/name,CTX/'private'/name)
    for p in [CTX,*CTX.rglob('*')]:
        require(not p.is_symlink(),'functional source symlink')
        os.chown(p,0,0);p.chmod(0o755 if p.is_dir() or p.stat().st_mode&0o111 else 0o644)
    for p in [CTX/'private',*list((CTX/'private').iterdir())]:
        os.chown(p,0,c['gid']);p.chmod(0o750 if p.is_dir() else 0o640)
    replacements={f'p3-h5r1-{label}-browser{suffix}':f'{label}-browser{suffix}'
                  for label in ('msd','hid') for suffix in ('-hil.py','.mjs')}
    # Fully reviewed VM source replaces only these four fresh copies.
    for name in source['files']:
        shutil.copyfile(HERE/name,CTX/'lab'/replacements.get(name,name))
        (CTX/'lab'/replacements.get(name,name)).chmod(0o644)
    # Keep original names too for source-hash verification in the copied launcher.
    for name in replacements:shutil.copyfile(HERE/name,CTX/'lab'/name);(CTX/'lab'/name).chmod(0o644)
    publish(CTX/'lab/functional-source-provenance.json',source,0o644)
    shutil.copytree(Path('/var/lib/blikvm-p3-h3/controller/preparation'),PREP,
                    ignore=shutil.ignore_patterns('__pycache__'))
    p=PREP/'collect.py';text=p.read_text()
    require(text.count('/var/lib/blikvm-p3-h3/controller/preparation')==1,'collector source context drift')
    p.write_text(text.replace('/var/lib/blikvm-p3-h3/controller/preparation',str(PREP)))
    f={'source':source,'runtime_contract_sha256':H['digest'](BASE/'input/contract.json'),
       'environment_additions':['NODE_EXTRA_CA_CERTS','P3_CONTROL','P3_LAUNCH_REQUIREMENTS','H5R1_HOST_NETNS'],
       'network':'normal bridge networking after accepted minimal replays',
       'cwd':c['cwd'],'home':c['home'],'launch_options':c['launch_options'],'xvfb_arguments':c['xvfb_arguments'],
       'executables':{n:{'sha256':H['digest'](Path(n).resolve())} for n in ['/usr/bin/node','/usr/bin/xvfb-run','/usr/bin/Xvfb','/usr/bin/xauth','/usr/bin/certutil','/usr/bin/xdotool']}}
    publish(CTX/'contract.json',f,0o644)
    publish(BASE/'controller/functional-source-provenance.json',source)
    publish(BASE/'controller/functional-input-manifest.json',P['manifest'](BASE/'input'))
    require(P['manifest'](P['RUNTIME'])==c['runtime_manifest'],'qualified runtime drift')
    publish(BASE/'controller/functional-prepared.json',{'target_contacted':False,'source_commit':source['commit'],
      'preparation_manifest':P['manifest'](PREP),'runtime_manifest_unchanged':P['manifest'](P['RUNTIME'])==c['runtime_manifest']})
    print('Functional inputs prepared; no target contact or browser launch')


def collect(label,run):
    p=subprocess.run(['/usr/bin/python3',str(PREP/'collect.py'),str(run/label)],capture_output=True,text=True,timeout=300)
    publish(run/(label+'-transport.json'),{'returncode':p.returncode,'stdout':p.stdout,'stderr':p.stderr})
    require(p.returncode==0,'inventory transport failed')
    inv=read(run/label/'target.json')
    runpy.run_path(str(PREP/'assess.py'))['assess'](inv,read(PREP/'p2-identity.json'))
    original=read(Path('/var/lib/blikvm-p3-legacy/blikvm-p3/a01/startup/target.json'))
    for key in ('boot_id','sd_cid','machine_id','host_public_keys','hash_checks'):
        require(inv[key]==original[key],'target continuity failed: '+key)
    def generations(r):
        return [line for key in ('services','ssh_show') for line in r['commands'][key]['stdout'].splitlines()
                if line.startswith(('Id=','InvocationID=','ExecMainStartTimestampMonotonic=','NRestarts='))]
    require(generations(inv)==generations(original),'target service generation changed')
    return inv


def inventory():
    source_check();prerequisites();P['idle']()
    run=BASE/'controller/target-continuity';P['mkdir'](run)
    try:
        r=collect('before-first-functional',run)
        publish(run/'result.json',{'result':'TARGET_CONTINUITY_PASS','hashes':10690,'boot_id':r['boot_id']})
    except BaseException as e:
        publish(BASE/'controller/FAILED.json',{'result':'FAILED','phase':'target-continuity','error':repr(e)})
        raise


def browser(label):
    require(label in ('msd','hid'),'invalid browser label')
    c=read(BASE/'input/contract.json')
    env=dict(c['environment'],NODE_EXTRA_CA_CERTS=str(CTX/'private/ca.crt'),
             P3_CONTROL=os.environ['P3_CONTROL'],P3_LAUNCH_REQUIREMENTS=os.environ['P3_LAUNCH_REQUIREMENTS'],
             H5R1_HOST_NETNS=os.readlink('/proc/self/ns/net'))
    os.setgroups(c['groups']);os.setgid(c['gid']);os.setuid(c['uid']);os.chdir(c['cwd']);os.umask(0o077)
    args=['/usr/bin/xvfb-run',*c['xvfb_arguments'],'/usr/bin/node',str(CTX/'lab'/(label+'-browser.mjs')),
          str(CTX/'private'),os.environ['P3_BROWSER_LEAF']]
    if label=='hid':args.append('functional')
    os.execve(args[0],args,env)


def functional(number):
    source_check();prerequisites();require(number in (1,2,3),'iteration')
    require(read(BASE/'controller/target-continuity/result.json')['result']=='TARGET_CONTINUITY_PASS','continuity missing')
    for i in range(1,number):
        name=f'functional-{i:03d}';ack=read(BASE/'controller'/(name+'-vm-replay.json'))
        require(ack['result']=='H5R1_FUNCTIONAL_ACCEPTED' and ack['leaf_archive_sha256']==read(BASE/'controller'/name/'result.json')['seal']['sha256'],'prior functional replay missing')
    P['idle']();name=f'functional-{number:03d}';run=BASE/'controller'/name;P['mkdir'](run)
    c=read(BASE/'input/contract.json');leaf=BASE/'active'/(name+'-'+uuid.uuid4().hex)
    r={'name':name,'result':'in_progress','qualification_credit':0,'accepted_cycles':0,'stages':[],'leaf':str(leaf)}
    publish(run/'start.json',r);before=None
    try:
        require(not list((BASE/'active').iterdir()),'extra leaf');P['mkdir'](leaf,owner=(c['uid'],c['gid']))
        require(P['manifest'](BASE/'input')==read(BASE/'controller/functional-input-manifest.json'),'functional input drift')
        before=P['protected']();publish(run/'protected-before.json',before)
        # Explicitly tests all sealed predecessors before any run's target contact.
        P['audit'](leaf,run/'before-target-audit.json')
        first=collect('before',run)
        publish(run/'boot-result.json',{'run_directory':'/home/user/blikvm-p2/attempt02/coldboot01','boot_id':first['boot_id'],'qualification_pass':False})
        for label in ('msd','hid'):
            output=leaf/label;P['mkdir'](output,owner=(c['uid'],c['gid']));P['reset_home']()
            control=run/label;P['mkdir'](control)
            ack=BASE/'input/acks'/(name+'-'+label);P['mkdir'](ack,0o755)
            req=P['audit'](leaf,run/(label+'-before-audit.json'))
            requirements=ack/'requirements.json';publish(requirements,req,0o644)
            env={'PATH':'/usr/sbin:/usr/bin:/sbin:/bin','LANG':'C.UTF-8','PYTHONDONTWRITEBYTECODE':'1',
                 'P3_BROWSER_LEAF':str(output),'P3_CONTROL':str(ack),'P3_LAUNCH_REQUIREMENTS':str(requirements)}
            with (control/'harness.log').open('x') as log:
                p=subprocess.run(['/usr/bin/python3',str(CTX/'lab'/(label+'-browser-hil.py')),
                    '--output',str(control),'--boot-result',str(run/'boot-result.json')],cwd=CTX,env=env,
                    stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,timeout=850,close_fds=True)
            P['idle']()
            result=read(control/'result.json');br=read(output/'browser-result.json')
            logs=(control/'browser.log').read_text();argv=[s for s in logs.splitlines() if '<launching>' in s]
            publish(control/'generated-argv.json',argv)
            gates=list(output.glob('launch-*-contract.json'))
            require(len(gates)==len(argv)==(2 if label=='msd' else 1),'missing prospective contract/argv')
            require('SIGTRAP' not in logs and p.returncode==0 and result['result']==br['result']=='passed','functional browser failed')
            P['mkdir'](output/'runtime-home')
            for f in list(P['HOME'].iterdir()):os.rename(f,output/'runtime-home'/f.name)
            require(P['protected']()==before,'protected history changed')
            r['stages'].append({'name':label,'result':'passed','launches':len(gates)})
        last=collect('after',run)
        r.update(result='FUNCTIONAL_PASS_PENDING_VM_REPLAY',hashes_matched=10690,boot_id=last['boot_id'])
    except BaseException as e:
        r.update(result='FAILED',error=repr(e));publish(BASE/'controller/FAILED.json',r)
    finally:
        try:
            r['browser_idle']=P['idle']()
            if list(P['HOME'].iterdir()):
                P['mkdir'](leaf/'failure-runtime-home')
                for f in list(P['HOME'].iterdir()):os.rename(f,leaf/'failure-runtime-home'/f.name)
            r['seal']=H['seal'](leaf,BASE)
            P['audit'](None,run/'after-seal-audit.json')
            after=P['protected']();publish(run/'protected-after.json',after)
            require(before==after and before is not None,'protected history changed')
            require(P['manifest'](BASE/'input')==read(BASE/'controller/functional-input-manifest.json'),'protected functional inputs changed')
            r['protected_inputs_unchanged']=True
        except BaseException as e:
            r.update(result='FAILED',preservation_error=repr(e))
            if not (BASE/'controller/FAILED.json').exists():publish(BASE/'controller/FAILED.json',r)
        r['finished_ns']=time.time_ns();publish(run/'result.json',r)
    print(json.dumps(r));require(r['result']!='FAILED','H5R1 stopped; no later preflight or P3 cycle')


if __name__=='__main__':
    require(os.geteuid()==0,'root controller required');os.umask(0o077)
    action=sys.argv[1]
    if action=='prepare':prepare()
    elif action=='inventory':inventory()
    elif action=='browser':browser(sys.argv[2])
    elif action=='functional':functional(int(sys.argv[2]))
    else:raise SystemExit('prepare | inventory | browser msd|hid | functional 1..3')
