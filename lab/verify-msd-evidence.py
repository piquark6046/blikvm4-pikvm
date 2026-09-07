#!/usr/bin/env python3
"""Offline replay of raw M8-E storage, HID, video, lifecycle and boot evidence."""
import argparse,ast,json,hashlib,re,runpy
from pathlib import Path
from types import SimpleNamespace
p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--preflight-only',action='store_true');a=p.parse_args()
H=runpy.run_path(str(Path(__file__).with_name('hid-api-hil.py')))
# Reuse the frozen independent HID/video checks without executing its M8-D manifest.
source=ast.parse(Path(__file__).with_name('verify-hid-evidence.py').read_text())
keep=[n for n in source.body if isinstance(n,ast.FunctionDef) or isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id in ('REPORTS','USB') for t in n.targets)]
result={'result':'failed','boots':[],'api_runs':0,'browser_stages':0,'video':[],'storage_checks':0,'msd_transitions':0}
exec(compile(ast.Module(body=keep,type_ignores=[]),'inherited-evidence-checks','exec'))
IMAGE=H['G4']['EXPECTED']['sha256'];MEDIA='/usr/share/kvmd-msd/images/g4-storage.img'
ENROLLED='dadf5f2839f42ae062f793a58a79afb5b2305f01e345a4c2434adbaca29467cb'
PACKAGE='228d2f6dc1114b4516943249d25ddf1f10e4161c9cb53c6603b286b2b4e7f85e'
def artifacts(boot):
    meta=read(a.root/'runs'/boot['run_id']/'metadata.json')['artifacts']
    expected={'Image':'d6f4235904b0b482e78f449139f539adc4370be923ec16f4a0d8451842501ee8',
              'sun50i-h616-blikvm-v4.dtb':'3dadd0efd2c9ded33d852446a32e9cd2de2a6989c1f01798c1ab3c6f49887ee2',
              'initramfs.cpio.gz':ENROLLED,'kvmd-web_4.213-1blikvm4_arm64.deb':PACKAGE}
    for name,sha in expected.items():assert meta[name]['sha256']==sha,(name,boot['run_id'])

def storage(path):
    for f in path.glob('storage-*.json'):
        r=read(f)
        if 'filesystem_write' not in r:continue
        assert r['passed'],str(f)
        assert r['image_sha256_before']==r['image_sha256_after']==IMAGE
        assert r['filesystem_write']['rejected'] and r['filesystem_write']['errno']==30
        s=r['scsi_write'];assert s['returncode']!=0
        assert 'data protect' in (s['stdout']+s['stderr']).lower() and 'write protected' in (s['stdout']+s['stderr']).lower()
        i=r['identity'];assert (i['ro'],i['size'],i['queue/logical_block_size'],i['type'])==('1','16384','512','0')
        assert (i['vendor'],i['model'],i['rev'])==('BliKVM','G4 RAM RO','0001')
        assert ':1.3' in i['interface'] and i['interface'] in i['sysfs']
        assert r['filesystem']['LABEL']=='BLIKVM_G4' and r['filesystem']['VERSION']=='FAT16'
        assert r['files']==H['G4']['EXPECTED']['files']
        result['storage_checks']+=1

def msd(path,browser_ui=False):
    r=passed(path/'result.json');assert r['transitions']
    for t in r['transitions']:
        label=t['label'];assert t['image_sha256']==IMAGE
        real=read(path/(label+'-target.stdout'));api_state=read(path/(label+'-api.json'))
        assert real['hash']==real['legacy_hash']==IMAGE
        assert real['lun']['file']==(MEDIA if t['connected'] else '')
        assert (real['lun']['ro'],real['lun']['cdrom'],real['lun']['removable'])==('1','0','0')
        assert all(v!=0 for v in real['permissions'].values())
        assert api_state['drive']['connected']==t['connected'] and not api_state['drive']['rw'] and not api_state['drive']['cdrom']
        assert set(api_state['storage']['images'])=={'g4-storage.img'}
        result['msd_transitions']+=1
    storage(path)
    if browser_ui:
        b=passed(path/'browser-result.json');assert not b['errors']
        assert len(r['stages'])==11 and all(s['result']=='passed' for s in r['stages'])
        stages={s['name']:s for s in b['steps']}
        assert stages['browser-close']['browser_process_closed']
        assert stages['logout-stale-websocket']['stale_socket_state']==3
        assert stages['logout-stale-websocket']['loggedout_status'] in (401,403)
        assert not stages['ui-eject']['connected'] and stages['ui-connect']['connected']
        assert (path/'connected.png').stat().st_size>10000
    else:
        assert len(r.get('denials',[]))>=25
        assert all(x['status'] in (400,401,403,404,405,409) for x in r['denials'])
        for t in r['transitions']:
            if t['connected']:continue
            label=t['label'];tur=path/(label+'-tur.log')
            if tur.exists():
                v=read(tur);assert v['returncode']==2 and 'Medium not present' in v['stderr']
                assert read(path/(label+'-read.log'))['returncode']!=0
    return r

def inventory(path):
    r=read(path);mapping(r)
    assert not r['failed_units'].strip() and r['msd_image_sha256']==IMAGE
    assert r['msd_lun']['ro']=='1' and r['msd_lun']['cdrom']=='0'
    kernel=r['logs']['target-dmesg']
    assert not re.search(r'(?:musb|scsi|usb-storage)[^\n]*(?:timed out|timeout|stall|error|failed)',kernel,re.I)
    assert not re.search(r'(?:WARNING:|BUG:|Call trace:)',kernel)
    return r

try:
    q=a.root/'qualification';pre=q/'final-preflight-narrow';artifacts(passed(pre/'result.json')['boot'])
    passed(pre/'privilege.stdout');inventory(pre/'inventory-before.stdout');inventory(pre/'inventory-after.stdout');passed(pre/'policy/result.json')
    life=msd(pre/'api-lifecycle');labels={t['label'] for t in life['transitions']}
    assert {service+'-'+str(state)+'-after' for service in ('kvmd','nginx') for state in (False,True)}<=labels
    msd(pre/'msd-browser',True)
    for name in ('two-client-storage','browser-storage'):
        path=pre/name;r=passed(path/'result.json');assert not r['host_transport_errors']
        lines=[json.loads(s) for s in (path/'reads.jsonl').read_text().splitlines()]
        assert len(lines)==r['direct_reads'] and len(lines)>=20
        assert all(s['bytes']==8388608 and s['sha256']==IMAGE and s['end']>s['start'] for s in lines)
        assert all(b['start']-c['end']<2 for c,b in zip(lines,lines[1:]))
        storage(path)
        video_path=path/'hid-video'/('two-clients' if name=='two-client-storage' else 'concurrent-video')
        measured=read(video_path/'result.json')['clients']
        for client in measured:
            start=client['measurement_start_unix'];end=start+client['elapsed']
            assert lines[0]['start']<=start and lines[-1]['end']>=end
        if name=='two-client-storage':
            dirs=[d for d in (path/'hid-video').glob('hid-[0-9]*') if d.is_dir()];assert len(dirs)>=10
            for d in dirs:api(d)
            video(path/'hid-video/two-clients',2)
        else:browser(path/'hid-video');video(path/'hid-video/concurrent-video',1)
    if not a.preflight_only:
        series=q/'five-boots-narrow';passed(series/'result.json')
        for n in range(1,6):
            path=series/('boot'+str(n));r=passed(path/'result.json')
            before=inventory(path/'inventory.stdout');after=inventory(path/'inventory-after.stdout')
            assert before['boot_id']==after['boot_id']==r['boot_id']
            assert before['msd_lun']['file']==MEDIA
            artifacts(r['boot'])
            passed(path/'privilege.stdout');passed(path/'policy/result.json');api(path/'hid-api');api(path/'hid-api-after');browser(path/'hid-browser')
            msd(path/'msd-api');msd(path/'msd-browser',True);passed(path/'helper-negative.stdout')
            result['boots'].append({'number':n,'boot_id':r['boot_id'],'run_id':r['boot']['run_id']})
        assert len({b['boot_id'] for b in result['boots']})==5
        path=q/'physical-reconnect';r=passed(path/'result.json')
        assert r['manual_target_repair'] is False and r['usb_sha256']==USB
        assert r['before_descriptors']==r['after_descriptors']
        assert read(path/'ready.json')['ready'] and read(path/'disconnected.json')['observed'] and read(path/'disconnected.json')['hid_objects_absent']
        assert read(path/'storage-absent-physical.json')['passed']
        assert inventory(path/'before-inventory.stdout')['boot_id']==inventory(path/'after-inventory.stdout')['boot_id']
        storage(path);api(path/'hid-api');msd(path/'msd-browser',True);browser(path/'hid-browser')
    result['scope']='preflight' if a.preflight_only else 'complete-M8-E'
    result['result']='passed'
except Exception as ex:result['error']=str(ex)
a.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result));raise SystemExit(result['result']!='passed')
