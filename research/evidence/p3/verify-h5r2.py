#!/usr/bin/env python3
"""Independent VM replay; inspect archive bytes, never execute archived code."""
import argparse
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import tarfile


def require(ok, why):
    if not ok:raise RuntimeError(why)


def entries(t):
    result={}
    for m in t:
        p=PurePosixPath(m.name)
        require(not p.is_absolute() and '..' not in p.parts and m.name not in result,'unsafe member')
        require(m.isfile() or m.isdir(),'special archive member')
        result[m.name]=m
    return result


sha=lambda b:hashlib.sha256(b).hexdigest()


def netns(before,after):
    require(before['netns']==after['netns']!=before['host_netns'],'netns IDs')
    require(not before['sockets'] and not after['sockets'],'socket inherited')
    require([x['ifname'] for x in json.loads(before['raw']['link']['stdout'])]==['lo'],'root links')
    require(list(after['interfaces'])==['lo'],'Node links')
    require([x['ifname'] for x in json.loads(after['raw']['link']['stdout'])]==['lo'],'UID links')
    for k,v in before['raw'].items():
        require(v['returncode']==(2 if k=='target_route' else 0),'root netlink exit')
    require('Network is unreachable' in before['raw']['target_route']['stderr'],'target route exists')
    for row in json.loads(before['raw']['addr']['stdout']):
        require(row['ifname']=='lo','address interface')
        for a in row['addr_info']:require(a['local']=='::1' or a['local'].startswith('127.'),'address')
    for k in ('route','route_all','route6'):
        require(all(x.get('dev')=='lo' and not x.get('gateway') for x in json.loads(before['raw'][k]['stdout'])),'root route')
    for k,v in after['raw'].items():require(v['status']==0,'UID netlink exit')
    for k in ('route','route6'):
        require(all(x.get('dev')=='lo' and not x.get('gateway') for x in json.loads(after['raw'][k]['stdout'])),'UID route')
    require((after['uid'],after['gid'],after['groups'])==(before['uid'],before['gid'],before['groups']),'UID drift')


def javascript_json(raw):
    # Independently reproduce JSON.parse/stringify number representation. The
    # immutable original is separately bound by the prospective SHA-256, so no
    # original metadata precision is discarded from the evidence.
    p=subprocess.run(['node','-e',
        "process.stdout.write(JSON.stringify(JSON.parse(require('node:fs').readFileSync(0,'utf8'))))"],
        input=raw,capture_output=True,check=True)
    return json.loads(p.stdout)


def replay(archive, expected, name):
    require(sha(archive.read_bytes())==expected,'outer hash')
    with tarfile.open(archive) as t:
        outer=entries(t)
        data=lambda n:t.extractfile(n).read()
        read=lambda n:json.loads(data(n))
        index_name='controller/export-'+name+'/SHA256.json'
        index=read(index_name)
        require(set(index)|{index_name}=={n for n,m in outer.items() if m.isfile()},'index coverage')
        for n,h in index.items():require(sha(data(n))==h,'member hash: '+n)
        c=read('input/contract.json');source=read('controller/source-provenance.json')
        require(source['clean'] and source['commit']==source['origin_main']==c['source_commit'],'source provenance')
        for n,h in source['files'].items():require(sha(data('input/'+n))==h,'source bytes')
        require(c['home']=='/var/lib/blikvm-p3-h5r2/home' and c['groups']==[c['gid']],'account')
        require(c['shell']=='/usr/sbin/nologin' and c['account_status'].split()[1]=='L','account lock')
        require(c['launch_options']=={'headless':False},'launch options')
        require(c['xvfb_arguments']==['-a','-s','-screen 0 1600x1200x24 -nolisten tcp'],'Xvfb')
        require('TMPDIR' not in c['environment'] and 'XDG_RUNTIME_DIR' not in c['environment'],'environment')
        require(c['chromium_sha256']=='481fea1516a1f2b76454664272f12cd9dd1f20117b21e1f1498e08bc7f872c00','Chromium pin')
        require(c['playwright_sha256']=='718c91812946dcfbb4b724cfa0084ee3be205c571df09094f218bc4571f43c2b','Playwright pin')
        selftest=read('controller/netns-selftest/result.json')
        require(selftest['result']=='NETNS_SELFTEST_PASS' and selftest['returncode']==0,'selftest')
        observations=[json.loads(x) for x in data('controller/netns-selftest/netns.log').decode().splitlines()]
        require(len(observations)==2,'selftest records')
        netns(observations[0]['pre_drop'],observations[1])
        r=read('controller/'+name+'/result.json');seal=r['seal']
        require(not r['target_contacted'] and r['accepted_cycles']==r['qualification_credit']==0,'scope')
        require(r['protected_inputs_unchanged'] and 'preservation_error' not in r,'preservation')
        require(read('controller/'+name+'/protected-before.json')==read('controller/'+name+'/protected-after.json'),'protected state')
        require(not r['browser_idle_after']['pids'] and not seal['browser_exit']['pids'],'process cleanup')
        for phase in ('before','after-seal'):
            a=read('controller/'+name+'/'+phase+'-audit.json');e=a['effective']
            require(a['returncode']==0 and all(x['passed'] for x in e['operations']),'permission audit')
            require((e['uid'],e['gid'],e['groups'])==(c['uid'],c['gid'],c['groups']),'audit identity')
            require(e['writable_leaves']==([r['leaf']] if phase=='before' else []),'writable leaves')
            if phase=='after-seal':require(seal['sealed'] in a['requirements']['barriers'],'seal barrier')
        archive_name='controller/'+PurePosixPath(seal['archive']).name
        require(sha(data(archive_name))==seal['sha256'],'leaf archive hash')
        metadata=read('controller/'+PurePosixPath(seal['manifest']).name)['paths']
        require(seal['method']=='atomic_rename_under_root_0700','seal method')
        with tarfile.open(fileobj=io.BytesIO(data(archive_name))) as inner:
            im=entries(inner)
            require(len(im)==len(metadata),'leaf coverage')
            for n,m in im.items():
                old=metadata[str(PurePosixPath(r['leaf']).parent/n)]
                current=outer['sealed/'+n]
                require((m.uid,m.gid,m.mode)==(old['uid'],old['gid'],old['mode'])==(current.uid,current.gid,current.mode),'leaf metadata')
                if m.isfile():require(sha(inner.extractfile(m).read())==sha(data('sealed/'+n))==old['sha256'],'leaf bytes')
        prefix='sealed/'+PurePosixPath(r['leaf']).name+'/'
        before=read('input/acks/'+name+'-requirements.netns.json')
        after=read(prefix+'netns-after-drop.json');netns(before,after)
        log=data('controller/'+name+'/browser-debug.log').decode()
        argv=[line for line in log.splitlines() if '<launching>' in line]
        require(argv==r['generated_argv_lines']==read('controller/'+name+'/generated-argv.json'),'argv capture')
        contract=read(prefix+'launch-contract.json')
        require(contract['phase']=='before_launch' and contract['frozen_contract']==javascript_json(data('input/contract.json')),'prospective contract')
        require(contract['contract_sha256']==sha(data('input/contract.json')),'contract hash')
        audit=read(prefix+'launch-audit.json')
        require(audit['operations'] and all(o['passed'] for o in audit['operations']),'launch audit')
        require((audit['uid'],audit['gid'],audit['groups'])==(c['uid'],c['gid'],c['groups']),'launch UID')
        if r['result']=='FAILED':
            require(read('controller/FAILED.json')['result']=='FAILED','failed latch')
            result='H5R2_FAILURE_CONFIRMED'
        else:
            require(r['result']=='MINIMAL_PASS_PENDING_VM_REPLAY' and r['returncode']==0,'minimal result')
            require('controller/FAILED.json' not in outer,'unexpected failure latch')
            require(len(argv)==1 and 'SIGTRAP' not in log,'browser argv or signal')
            require('<process did exit: exitCode=0, signal=null>' in log,'clean browser exit')
            browser=read(prefix+'result.json')
            require(browser['result']=='MINIMAL_BROWSER_PASS' and browser['stages']==['launch','context','page','about:blank','context-close','browser-close'],'browser stages')
            result='H5R2_MINIMAL_ACCEPTED'
        return dict(result=result,name=name,source_commit=source['commit'],archive_sha256=expected,
                    leaf_archive_sha256=seal['sha256'],indexed_files=len(index),netns_selftest='PASS',
                    prospective_contracts=1,generated_argv_records=len(argv),sigtrap='SIGTRAP' in log,
                    protected_inputs_unchanged=True,target_contacted=False,qualification_credit=0,
                    h5_status='FAILED',h3_root_cause='UNASSIGNED')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('archive',type=Path);p.add_argument('--sha256',required=True)
    p.add_argument('--name',required=True);a=p.parse_args()
    print(json.dumps(replay(a.archive,a.sha256,a.name),indent=2))
