#!/usr/bin/env python3
"""Replay H5R1 functional-001 failure without retrying or executing archive code."""
import argparse
import ast
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import runpy
import shlex
import tarfile

if not __debug__:raise SystemExit('assertions required')
V=runpy.run_path(str(Path(__file__).with_name('verify-h5r1.py')))
assess=runpy.run_path(str(Path(__file__).with_name('inventory-gates.py')))['assess']
sha=lambda b:hashlib.sha256(b).hexdigest()


def replay(archive, expected):
    assert sha(archive.read_bytes())==expected
    with tarfile.open(archive) as t:
        outer=V['entries'](t);data=lambda n:t.extractfile(n).read();read=lambda n:json.loads(data(n))
        idx='controller/export-functional-001-failed/SHA256.json';index=read(idx)
        assert set(index)|{idx}=={n for n,m in outer.items() if m.isfile()}
        for n,h in index.items():assert sha(data(n))==h,n
        r=read('controller/functional-001/result.json');latch=read('controller/FAILED.json')
        assert r['result']==latch['result']=='FAILED'
        assert r['qualification_credit']==r['accepted_cycles']==0 and r['stages']==[]
        assert r['error']=="RuntimeError('missing prospective contract/argv')"
        assert not any('functional-002' in n or 'functional-003' in n for n in outer)
        assert not any(n.startswith('controller/functional-001/hid/') for n in outer)
        assert r['protected_inputs_unchanged'] and 'preservation_error' not in r
        assert read('controller/functional-001/protected-before.json')==read('controller/functional-001/protected-after.json')
        seal=r['seal'];assert not r['browser_idle']['pids'] and not seal['browser_exit']['pids']
        assert seal['method']=='atomic_rename_under_root_0700'
        inner_name='controller/'+Path(seal['archive']).name;assert sha(data(inner_name))==seal['sha256']
        metadata=read('controller/'+Path(seal['manifest']).name)['paths']
        with tarfile.open(fileobj=io.BytesIO(data(inner_name))) as inner:
            im=V['entries'](inner);assert len(im)==len(metadata)==49
            for n,m in im.items():
                old=metadata[str(PurePosixPath(r['leaf']).parent/n)];new=outer['sealed/'+n]
                assert (m.uid,m.gid,m.mode)==(old['uid'],old['gid'],old['mode'])==(new.uid,new.gid,new.mode)
                if m.isfile():assert sha(inner.extractfile(m).read())==sha(data('sealed/'+n))==old['sha256']
        c=read('input/contract.json');fc=read('input/functional/contract.json')
        source=read('controller/source-provenance.json')
        assert source['clean'] and source['commit']==source['origin_main']==c['source_commit']=='ac73300f7b2633b36f0f8cde383845414282daad'
        for n,h in source['files'].items():assert sha(data('input/'+n))==h,n
        assert fc['source']['clean'] and fc['source']['commit']==fc['source']['origin_main']=='043fa5b94b6a3cfcd6dd90d2d0a440b5acb3da9e'
        for n,h in fc['source']['files'].items():assert sha(data('input/functional/lab/'+n))==h,n
        assert (c['uid'],c['gid'],c['groups'])==(993,981,[981])
        operations=0
        for phase in ('before-target','msd-before','after-seal'):
            a=read('controller/functional-001/'+phase+'-audit.json');e=a['effective']
            assert a['returncode']==0 and e['operations'] and all(o['passed'] for o in e['operations'])
            assert (e['uid'],e['gid'],e['groups'])==(993,981,[981])
            assert e['writable_leaves']==([] if phase=='after-seal' else [r['leaf']])
            operations+=len(e['operations'])
            if phase=='after-seal':
                assert seal['sealed'] in a['requirements']['barriers']
                assert any(o['path']==seal['sealed'] and o['operation']=='traverse' and o['errno']==13 for o in e['operations'])
                assert any(o['path'].startswith(seal['sealed']+'/') and o['operation']=='create' and o['errno']==13 for o in e['operations'])
        prefix='sealed/'+Path(r['leaf']).name+'/msd/'
        con=read(prefix+'launch-001-contract.json');audit=read(prefix+'launch-001-audit.json')
        assert con['phase']=='before_launch'
        assert con['frozen_contract']==V['javascript_json'](data('input/contract.json'))
        assert con['functional_contract']==V['javascript_json'](data('input/functional/contract.json'))
        assert con['contract_sha256']==sha(data('input/contract.json'))
        assert con['functional_contract_sha256']==sha(data('input/functional/contract.json'))
        assert con['launch_options']=={'headless':False} and con['cwd']==c['cwd']
        assert con['xvfb_arguments']==['-a','-s','-screen 0 1600x1200x24 -nolisten tcp']
        env=con['full_environment'];assert env['HOME']==c['home'] and env['DEBUG']=='pw:browser*'
        assert 'TMPDIR' not in env and 'XDG_RUNTIME_DIR' not in env
        assert con['network']['netns']==env['H5R1_HOST_NETNS'] and not con['network']['sockets']
        assert audit['operations'] and all(o['passed'] for o in audit['operations'])
        assert (audit['uid'],audit['gid'],audit['groups'])==(993,981,[981])
        operations+=len(audit['operations'])
        log=data('controller/functional-001/msd/browser.log').decode()
        argv=[s for s in log.splitlines() if '<launching>' in s]
        assert argv==read('controller/functional-001/msd/generated-argv.json') and len(argv)==1
        assert 'SIGTRAP' not in log and log.count('<process did exit: exitCode=0, signal=null>')==1
        def flags(line):
            tokens=shlex.split(line.split('<launching> ',1)[1])
            profiles=[x for x in tokens if x.startswith('--user-data-dir=')]
            assert len(profiles)==1 and profiles[0].startswith('--user-data-dir=/tmp/playwright_chromiumdev_profile-')
            return [x for x in tokens if not x.startswith('--user-data-dir=')]
        assert flags(argv[0])==flags(read('controller/minimal-001/result.json')['generated_argv_lines'][0])
        ready=read(prefix+'001.ready');assert ready=={'name':'normal-login','connected':True}
        browser=read(prefix+'browser-result.json');msd=read('controller/functional-001/msd/result.json')
        assert browser['result']==msd['result']=='failed' and browser['steps']==[] and browser['errors']==[]
        assert len(msd['stages'])==1 and msd['stages'][0]['name']=='normal-login' and msd['stages'][0]['result']=='failed'
        actual=ast.literal_eval(msd['stages'][0]['error'])
        assert actual['drive']['connected'] is False and actual['drive']['rw'] is False
        assert actual['enabled'] and actual['online'] and not actual['busy']
        assert actual['drive']['image']['name']=='g4-storage.img' and not actual['drive']['image']['writable']
        assert msd['transitions']==[] and browser['version']=='145.0.7632.6'
        initial=read('controller/target-continuity/before-first-functional/target.json')
        before=read('controller/functional-001/before/target.json')
        after=read('controller/functional-001/failure-preservation/target.json')
        identity=read('controller/functional-preparation/p2-identity.json')
        for inv in (initial,before,after):assess(inv,identity)
        for key in ('boot_id','sd_cid','machine_id','host_public_keys','hash_checks','gadget'):
            assert initial[key]==before[key]==after[key],key
        lun='functions/mass_storage.g4/lun.0/'
        assert initial['gadget'][lun+'file']=='' and bytes.fromhex(initial['gadget'][lun+'ro']).strip()==b'1'
        def gen(inv):
            return [l for key in ('services','ssh_show') for l in inv['commands'][key]['stdout'].splitlines()
                    if l.startswith(('Id=','InvocationID=','ExecMainStartTimestampMonotonic=','NRestarts='))]
        assert gen(initial)==gen(before)==gen(after)
        journal=[json.loads(l) for l in after['commands']['journal_json']['stdout'].splitlines()]
        # Existing frozen classification of retained startup/logout errors.
        errors=[]
        for e in journal:
            message=str(e.get('MESSAGE',''))
            if not re.search(r'\bERROR\b|\bCRITICAL\b|Traceback|\[error\]|\[crit\]|segfault|EXT4-fs error|I/O error|Buffer I/O|Kernel panic|Oops:|checksum error',message):continue
            ts=int(e['__MONOTONIC_TIMESTAMP'])
            if ts<12_000_000:
                assert 9_000_000<=ts
                assert 'connect() to unix:/run/kvmd/api/kvmd.sock failed (2: No such file or directory)' in message or 'auth request unexpected status: 502' in message
                errors.append('historical-startup')
            else:
                assert e['_SYSTEMD_UNIT']=='nginx.service'
                assert 'recv() failed (104: Connection reset by peer) while proxying upgraded connection' in message
                assert re.search(r'request: "GET /api/ws(?:\?stream=false)? HTTP/1.1"',message)
                auth=[j for j in journal if j.get('_SYSTEMD_UNIT')=='kvmd.service' and ('Logged out user ' in str(j.get('MESSAGE','')) or 'Logged in user ' in str(j.get('MESSAGE','')))]
                preceding=[j for j in auth if int(j['__MONOTONIC_TIMESTAMP'])<ts];following=[j for j in auth if int(j['__MONOTONIC_TIMESTAMP'])>ts]
                assert preceding and 'Logged out user ' in preceding[-1]['MESSAGE']
                assert following and 'Logged in user ' in following[0]['MESSAGE']
                start=int(preceding[-1]['__MONOTONIC_TIMESTAMP']);end=int(following[0]['__MONOTONIC_TIMESTAMP'])
                assert any('Removed client socket:' in str(j.get('MESSAGE','')) and start<=int(j['__MONOTONIC_TIMESTAMP'])<end for j in journal)
                errors.append('historical-logout-reset')
        return {'result':'H5R1_FUNCTIONAL_FAILURE_CONFIRMED','archive_sha256':expected,'indexed_files':len(index),
            'minimal_launches_accepted':3,'functional_runs_passed':0,'functional_runs_failed':1,
            'functional_chromium_launches':1,'prospective_contracts':1,'generated_argv_records':1,
            'chromium_clean_exit':True,'sigtrap':False,'first_failure':'MSD normal-login expected connected=true; observed false',
            'controller_secondary_error':'missing prospective contract/argv (expected two launches; only first was reached)',
            'msd_backing_file_empty_before_and_after':True,'target_hashes_matched':10690,
            'target_boot_and_service_generations_unchanged':True,'protected_inputs_unchanged':True,
            'permission_operations':operations,'sealed_members':49,'browser_processes_remaining':0,
            'journal_records_reviewed':len(journal),'classified_historical_errors':errors,
            'h5_status':'FAILED','h3_root_cause':'UNASSIGNED','h5r1_status':'FAILED',
            'qualification_credit':0,'accepted_cycles':0,'p3_a_started':False}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('archive',type=Path);p.add_argument('--sha256',required=True)
    p.add_argument('--h5-history',type=Path);a=p.parse_args()
    result=replay(a.archive,a.sha256)
    if a.h5_history:
        assert sha(a.h5_history.read_bytes())=='304bdf020fdb6df9039fe459c392b6c22e16b9f8a04bd52900974430458bc0da'
        with tarfile.open(a.archive) as current:
            protected=json.load(current.extractfile('controller/functional-001/protected-after.json'))['/var/lib/blikvm-p3-h5']
        count=0
        with tarfile.open(a.h5_history) as historical:
            for n,m in V['entries'](historical).items():
                if m.isfile():
                    assert sha(historical.extractfile(m).read())==protected[n]['sha256'],n
                    count+=1
        result['h5_original_archived_files_unchanged']=count
    print(json.dumps(result,indent=2))
