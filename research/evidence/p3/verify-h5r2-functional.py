#!/usr/bin/env python3
"""Independent H5R2 functional archive and frozen browser/HID/SCSI replay."""
import argparse
import ast
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import runpy
import shutil
import shlex
import tarfile
import tempfile

if not __debug__:raise SystemExit('assertions required')
REPO=Path(__file__).resolve().parents[3]
V=runpy.run_path(str(Path(__file__).with_name('verify-h5r2.py')))
H=runpy.run_path(str(REPO/'lab/hid-api-hil.py'))
assess=runpy.run_path(str(Path(__file__).with_name('inventory-gates.py')))['assess']
sha=lambda b:hashlib.sha256(b).hexdigest()
read=lambda p:json.loads(p.read_bytes())
def passed(p):
    r=read(p);assert r['result']=='passed',(p,r.get('error'));return r
result={'storage_checks':0,'msd_transitions':0}
source=ast.parse((REPO/'lab/verify-msd-evidence.py').read_text())
keep=[n for n in source.body if isinstance(n,ast.FunctionDef) and n.name in ('storage','msd')]
IMAGE=H['G4']['EXPECTED']['sha256'];MEDIA='/usr/share/kvmd-msd/images/g4-storage.img'
exec(compile(ast.Module(body=keep,type_ignores=[]),'frozen-msd-replay','exec'))


def replay(archive, expected, name):
    assert sha(archive.read_bytes())==expected
    with tempfile.TemporaryDirectory(prefix='h5r2-functional-replay-') as temporary,tarfile.open(archive) as t:
        outer=V['entries'](t);data=lambda n:t.extractfile(n).read();j=lambda n:json.loads(data(n))
        idx='controller/export-'+name+'/SHA256.json';index=j(idx)
        assert set(index)|{idx}=={n for n,m in outer.items() if m.isfile()}
        for n,h in index.items():assert sha(data(n))==h,n
        r=j('controller/'+name+'/result.json');seal=r['seal']
        assert r['result']=='FUNCTIONAL_PASS_PENDING_VM_REPLAY' and 'controller/FAILED.json' not in outer
        assert r['qualification_credit']==r['accepted_cycles']==0 and r['hashes_matched']==10690
        assert r['protected_inputs_unchanged'] and not r['browser_idle']['pids']
        assert j('controller/'+name+'/protected-before.json')==j('controller/'+name+'/protected-after.json')
        assert seal['method']=='atomic_rename_under_root_0700' and not seal['browser_exit']['pids']
        inner_name='controller/'+Path(seal['archive']).name;assert sha(data(inner_name))==seal['sha256']
        metadata=j('controller/'+Path(seal['manifest']).name)['paths']
        with tarfile.open(fileobj=io.BytesIO(data(inner_name))) as inner:
            im=V['entries'](inner);assert len(im)==len(metadata)
            for n,m in im.items():
                old=metadata[str(PurePosixPath(r['leaf']).parent/n)];new=outer['sealed/'+n]
                assert (m.uid,m.gid,m.mode)==(old['uid'],old['gid'],old['mode'])==(new.uid,new.gid,new.mode)
                if m.isfile():assert sha(inner.extractfile(m).read())==sha(data('sealed/'+n))==old['sha256']
        c=j('input/contract.json');fc=j('input/functional/contract.json')
        assert fc['source']['clean'] and fc['source']['commit']==fc['source']['origin_main']
        for n,h in fc['source']['files'].items():assert sha(data('input/functional/lab/'+n))==h,n
        for phase in ('before-target','msd-before','hid-before','after-seal'):
            a=j('controller/'+name+'/'+phase+'-audit.json');e=a['effective']
            assert a['returncode']==0 and e['operations'] and all(o['passed'] for o in e['operations'])
            assert (e['uid'],e['gid'],e['groups'])==(c['uid'],c['gid'],c['groups'])
            for prior in range(1,int(name[-3:])):
                old=j('controller/'+f'functional-{prior:03d}'+'/result.json')['seal']['sealed']
                assert old in a['requirements']['barriers']
                assert any(o['path']==old and o['operation']=='traverse' and o['errno'] in (1,13,30) for o in e['operations'])
        prefix='sealed/'+Path(r['leaf']).name+'/'
        def stable_argv(line):
            values=shlex.split(line.split('<launching> ',1)[1])
            profiles=[x for x in values if x.startswith('--user-data-dir=')]
            assert len(profiles)==1 and profiles[0].startswith('--user-data-dir=/tmp/playwright_chromiumdev_profile-')
            return [x for x in values if not x.startswith('--user-data-dir=')]
        minimal_argv=stable_argv(j('controller/minimal-001/result.json')['generated_argv_lines'][0])
        launches=0
        for label,total in (('msd',2),('hid',1)):
            log=data('controller/'+name+'/'+label+'/browser.log').decode()
            argv=[s for s in log.splitlines() if '<launching>' in s]
            assert argv==j('controller/'+name+'/'+label+'/generated-argv.json') and len(argv)==total
            assert all(stable_argv(line)==minimal_argv for line in argv)
            assert 'SIGTRAP' not in log and log.count('<process did exit: exitCode=0, signal=null>')==total
            for i in range(1,total+1):
                root=prefix+label+f'/launch-{i:03d}'
                con=j(root+'-contract.json');audit=j(root+'-audit.json')
                assert con['phase']=='before_launch' and con['frozen_contract']==V['javascript_json'](data('input/contract.json'))
                assert con['functional_contract']==V['javascript_json'](data('input/functional/contract.json'))
                assert con['contract_sha256']==sha(data('input/contract.json')) and con['functional_contract_sha256']==sha(data('input/functional/contract.json'))
                assert (con['uid'],con['gid'],con['groups'])==(c['uid'],c['gid'],c['groups'])
                assert con['cwd']==c['cwd'] and con['launch_options']=={'headless':False} and con['xvfb_arguments']==c['xvfb_arguments']
                env=con['full_environment'];assert env['HOME']==c['home'] and env['DEBUG']=='pw:browser*'
                assert 'TMPDIR' not in env and 'XDG_RUNTIME_DIR' not in env and not con['network']['sockets']
                assert con['network']['netns']==env['H5R1_HOST_NETNS']
                assert audit['operations'] and all(o['passed'] for o in audit['operations'])
                assert (audit['uid'],audit['gid'],audit['groups'])==(c['uid'],c['gid'],c['groups'])
                launches+=1
        # Verified regular-file-only archive, extracted solely into disposable VM space.
        t.extractall(temporary,filter='data');root=Path(temporary);run=root/'controller'/name
        before=read(run/'before/target.json');after=read(run/'after/target.json')
        identity=read(root/'controller/functional-preparation/p2-identity.json')
        for inv in (before,after):assess(inv,identity)
        first=read(root/'controller/target-continuity/before-first-functional/target.json')
        for key in ('boot_id','sd_cid','machine_id','host_public_keys','hash_checks'):
            assert before[key]==after[key]==first[key],key
        assert before['boot_id']=='1c8365c7-90bf-46fb-8db4-5ec06a745a6a'
        for label in ('before','after'):
            gate='controller/'+name+'/'+label+'-msd-gate/'
            assert j(gate+'result.json')['result']=='ATTACHED_MSD_PREREQUISITE_PASS'
            runpy.run_path(str(REPO/'lab/p3-h5r2-state.py'))['check'](j('controller/'+name+'/'+label+'/target.json'),j(gate+'target-state.json'),j(gate+'host.json'))
        def generations(inv):
            return [l for key in ('services','ssh_show') for l in inv['commands'][key]['stdout'].splitlines()
                    if l.startswith(('Id=','InvocationID=','ExecMainStartTimestampMonotonic=','NRestarts='))]
        assert generations(before)==generations(after)==generations(first)
        # Reunite controller and browser files in a VM-only view for frozen replayers.
        view=root/'replay-view';view.mkdir()
        for label in ('msd','hid'):
            d=view/label;shutil.copytree(run/label,d)
            browser=root/prefix/label
            for p in browser.iterdir():
                if p.is_file():assert not (d/p.name).exists();shutil.copyfile(p,d/p.name)
        msd(view/'msd',True)
        assert result['storage_checks']==sum(x['connected'] for x in read(REPO/'lab/p3-h3-protocol.json')['msd'])
        path=view/'hid'
        h=passed(path/'result.json');b=passed(path/'browser-result.json')
        assert not b['errors']
        assert h['usb_descriptor_sha256']=='733b5003b2c57a865b6366a1e4a8aa6429e9a6d3a827a79b64ba8473b445a52e'
        assert h['host_repeat']['during']==[0,0] and h['host_repeat']['restore_on_exit']
        assert not re.search(r'usb[^\n]*(?:disconnect|reset)',(path/'host-kernel-live.log').read_text(),re.I)
        names={s['name'] for s in b['steps']}
        assert {'keyboard','absolute-near-min','absolute-center','absolute-near-max','relative-0-0','relative-2-4','browser-close-cleanup','websocket-close-cleanup','logout-cleanup-and-stale-socket','video-motion','final-close'}<=names
        count=0
        for f in sorted(path.glob('*-evdev.json')):
         ev=passed(f);actual=[H['frames'](x) for x in ev['raw']];assert actual==ev['actual'],str(f)
         kind=ev['spec']['kind'];d=ev['details']
         assert ev['held']==ev['spec'].get('held',[[],[],[]])
         if kind=='exact':assert actual==d['expected']
         elif kind=='absolute':
          assert not actual[0] and not actual[2] and actual[1] and d['tolerance']==1
          assert abs(ev['axes']['0']['value']-d['x'])<=1 and abs(ev['axes']['1']['value']-d['y'])<=1
         elif kind=='relative':
          assert not actual[0] and not actual[1] and actual[2]
          assert [v for v in d['moves'] if any(v)]==[d['requested']]
          expected=[]
          for packet in d['sent']:
           if packet[0]!=4:continue
           assert packet[1]==1 and len(packet)==4
           pair=[v-256 if v>127 else v for v in packet[2:]]
           expected.append([[2,i,v] for i,v in enumerate(pair) if v])
          assert actual[2]==expected
         else:assert kind=='setup','unexpected restart or stage'
         if ev['spec']['name']=='logout-cleanup-and-stale-socket':assert d['staleSocket']==3 and d['staleHttp'] in (401,403)
         count+=1
        motion=next(x for x in b['steps'] if x['name']=='video-motion')['hashes']
        assert len(motion)==6 and len(set(motion))>=4
        # The frozen P3 JavaScript has four mode-switch iterations and no service-restart stages.
        expected_names=['login-and-open','keyboard','absolute-near-min','absolute-center','absolute-near-max','absolute-button']
        for n in range(4):
         mode='usb' if n%2 else 'usb_rel'
         expected_names += [f'prepare-mode-{n}',f'mode-{mode}-{n}',f'close-menu-{n}']
         expected_names += ([f'absolute-return-{n}'] if n%2 else [f'pointer-lock-{n}']+[f'relative-{n}-{j}' for j in range(5)]+[f'relative-button-{n}'])
        expected_names += ['focus-keyboard','browser-held-shift','browser-close-cleanup','reopen','api-websocket-open','websocket-held-shift','websocket-close-cleanup','revocation-socket-open','logout-held-input','logout-cleanup-and-stale-socket','reauth','video-motion','final-close']
        assert [s['name'] for s in b['steps']]==[s['name'] for s in h['steps']]==expected_names
        assert count==len(expected_names)
        # Review every retained post-preflight journal message, not only priority fields.
        journal=[json.loads(l) for l in after['commands']['journal_json']['stdout'].splitlines()]
        errors=[]
        for e in journal:
         message=str(e.get('MESSAGE',''))
         if re.search(r'\bERROR\b|\bCRITICAL\b|Traceback|\[error\]|\[crit\]|segfault|EXT4-fs error|I/O error|Buffer I/O|Kernel panic|Oops:|checksum error',message):
          errors.append(e)
        startup_errors=[];logout_resets=[]
        for e in errors:
         message=str(e['MESSAGE']);ts=int(e['__MONOTONIC_TIMESTAMP'])
         if ts<12_000_000:
          assert 9_000_000<=ts
          assert 'connect() to unix:/run/kvmd/api/kvmd.sock failed (2: No such file or directory)' in message or 'auth request unexpected status: 502' in message
          startup_errors.append(ts)
         else:
          assert e['_SYSTEMD_UNIT']=='nginx.service'
          assert 'recv() failed (104: Connection reset by peer) while proxying upgraded connection' in message
          assert re.search(r'request: "GET /api/ws(?:\?stream=false)? HTTP/1.1"',message)
          auth=[j for j in journal if j.get('_SYSTEMD_UNIT')=='kvmd.service' and
                ('Logged out user ' in str(j.get('MESSAGE','')) or 'Logged in user ' in str(j.get('MESSAGE','')))]
          preceding=[j for j in auth if int(j['__MONOTONIC_TIMESTAMP'])<ts]
          following=[j for j in auth if int(j['__MONOTONIC_TIMESTAMP'])>ts]
          assert preceding and 'Logged out user ' in preceding[-1]['MESSAGE']
          assert following and 'Logged in user ' in following[0]['MESSAGE']
          start=int(preceding[-1]['__MONOTONIC_TIMESTAMP']);end=int(following[0]['__MONOTONIC_TIMESTAMP'])
          assert any('Removed client socket:' in str(j.get('MESSAGE','')) and
                     start<=int(j['__MONOTONIC_TIMESTAMP'])<end for j in journal)
          logout_resets.append({'reset_us':ts,'logout_us':start,'reauth_us':end})
        # Bounded journals may have evicted historical startup records; classify
        # every retained record without requiring evicted records to persist.
        result.update(result='H5R2_FUNCTIONAL_ACCEPTED',name=name,archive_sha256=expected,
            leaf_archive_sha256=seal['sha256'],functional_source_commit=fc['source']['commit'],
            target_hashes_matched=10690,service_generations_unchanged=True,launches=launches,
            prospective_contracts=launches,generated_argv_records=launches,hid_stages=count,
            video_unique_frames=len(set(motion)),journal_records_reviewed=len(journal),
            intentional_logout_socket_resets=logout_resets,qualification_credit=0,accepted_cycles=0,
            h5_status='FAILED',h3_root_cause='UNASSIGNED')
        return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('archive',type=Path);p.add_argument('--sha256',required=True)
    p.add_argument('--name',required=True);a=p.parse_args()
    print(json.dumps(replay(a.archive,a.sha256,a.name),indent=2))
