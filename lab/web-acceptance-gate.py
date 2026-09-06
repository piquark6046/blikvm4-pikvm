#!/usr/bin/env python3
"""Replay M8-B acceptance from raw streams, browser checks and both USB ends."""
import argparse
import datetime
import hashlib
import json
from pathlib import Path
import re
import runpy

HERE=Path(__file__).resolve().parent
VIDEO=runpy.run_path(str(HERE/'kvmd-gate.py'))
REBOOTS=runpy.run_path(str(HERE/'ubuntu-reboot-gate.py'))


def read(path):
    return json.loads(path.read_text())


def browser_gate(path, lifecycle=False):
    r=read(path/'result.json')
    assert r['result']=='passed'
    assert hashlib.sha256((path/'runner.mjs').read_bytes()).hexdigest()==r['automation_sha256']
    expected={'unauthenticated API':{401}, 'unauthenticated video':{401},
              'unauthenticated web redirected to login':{302}, 'invalid credentials':{403},
              'valid credentials':{200},'authenticated API':{200},'authenticated video':{200},
              'logout':{200},'logged-out API':{401,403},'logged-out video':{401,403}}
    rows={x['label']:x for x in r['http']}
    for name,statuses in expected.items():
        assert rows[name]['status'] in statuses,name
    for name in ('hid','msd','atx','gpio','switch'):
        assert rows['excluded '+name]['status']==404
    for name in ('vnc','ipmi'):
        assert rows['excluded page '+name]['status']==404
    ws={x['label']:x for x in r['websockets']}
    assert not ws['unauthenticated']['ok'] and not ws['logged-out']['ok']
    assert ws['authenticated']['ok'] and {'streamer','pong'}.issubset(ws['authenticated']['events'])
    assert r['tls']['verified'] and r['tls']['protocol'] in ('TLSv1.2','TLSv1.3')
    ui=r['browser']
    assert ui['logout'] and not ui['errors']
    assert ui['cookie']=={'secure':True,'httpOnly':True,'sameSite':'Strict'}
    assert len(ui['assets'])>10 and all(x['status']<400 for x in ui['assets'])
    assert (path/'browser.png').read_bytes().startswith(b'\x89PNG\r\n\x1a\n')
    phases=['initial','reload','after_rate_gate']
    if lifecycle:
        assert ui['lifecycle'] and ui['kvmd_restart_statuses'][-1] in (401,403)
        assert len(ui['hdmi_loss']['hashes'])==4 and len(set(ui['hdmi_loss']['hashes']))==1
        phases+=['nginx_restart','kvmd_restart_reauthenticated','hdmi_recovered']
    for phase in phases:
        value=ui[phase]
        assert (value['width'],value['height'])==(1920,1080)
        assert len(value['hashes'])==6 and len(set(value['hashes']))>=4
    stream=VIDEO['audit_stream'](path/'stream')
    assert stream['seconds_requested']>=120
    assert stream['frames']/stream['elapsed']>=27
    return {'fps':stream['frames']/stream['elapsed'],'frames':stream['frames'],
            'unique_hashes':stream['unique_hashes'],'tls_fingerprint':r['tls']['fingerprint256']}


def inventory_gate(path, allow_restart=False):
    r=read(path);assert r['result']=='passed'
    assert sorted((x['address'],x['port']) for x in r['listeners_proc'])==[
        ('127.0.0.1',443),('192.168.88.2',22)]
    assert r['ustreamer']['ppid']==r['kvmd_pid']
    assert r['ustreamer']['uid'].split()==['988']*4
    assert r['ustreamer']['gid'].split()==['989']*4
    assert r['ustreamer_version']=='6.65-1blikvm2'
    assert r['ustreamer_sha256']=='e5a489c828299bc28de71789414312510198c6d7da63b2b18c300bef6313e71b'
    args=r['ustreamer']['cmdline'].split()
    assert args==['/usr/bin/ustreamer','--device=/dev/kvmd-video','--resolution=1920x1080',
                  '--desired-fps=30','--device-fps=30','--quality=0','--format=MJPEG','--encoder=HW',
                  '--unix=/run/kvmd/ustreamer/ustreamer.sock','--unix-mode=0660','--unix-rm',
                  '--exit-on-parent-death','--notify-parent','--no-log-colors']
    assert '30.000 (30/1)' in r['logs']['video-mode']
    assert 'worker_shutdown_timeout 2s;' in r['logs']['nginx-effective']
    for journal in ('kvmd-journal','nginx-journal'):
        for line in r['logs'][journal].splitlines():
            if 'Got access denied for user' in line:continue  # Explicit invalid-password gate.
            assert not re.search(r'ERROR|Traceback|timed out|Failed with result',line),line
    backend=[]
    for line in r['logs']['nginx-error'].splitlines():
        if any(f'"GET /{name}/ HTTP/1.1"' in line and 'is not found' in line
               for name in ('vnc','ipmi')):
            continue  # Explicit excluded-page probes, not required assets.
        assert allow_restart and 'connect() to unix:/run/kvmd/api/kvmd.sock failed' in line,line
        assert 'GET /api/auth/check HTTP/1.1' in line,line
        backend.append(datetime.datetime.strptime(line[:19],'%Y/%m/%d %H:%M:%S'))
    if backend:
        assert len(backend)<=30 and (max(backend)-min(backend)).total_seconds()<=10
    return r


def exposure_gate(path):
    r=read(path);assert r['result']=='passed' and r['target']=='192.168.88.2'
    assert {x['port'] for x in r['probes']}=={22,80,443,8000,8080}
    assert all((x['connect_errno']==0)==(x['port']==22) for x in r['probes'])


def hil_gate(path,full=False):
    r=read(path/'test-results.json');assert r['result']=='passed'
    assert r['storage']['passed'] and r['concurrent_storage']['passed']
    assert set(r['hid'])=={'keyboard','absolute','relative'}
    assert all(x['passed'] for x in r['hid'].values())
    assert not r['usb_errors'] and not r.get('uart_errors') and not r.get('cleanup_error')
    VIDEO['audit_api'](path,11 if full else 2)
    api=read(path/'api-sustained.json')
    assert api['state_before']['streamer']['encoder']=={'type':'HW','quality':0}
    assert api['state_before']['streamer']['source']['resolution']=={'width':1920,'height':1080}
    assert api['state_before']['params']['desired_fps']==30
    s=VIDEO['audit_stream'](path/'sustained')
    assert s['seconds_requested'] >= (120 if full else 15)
    assert s['frames']>=s['seconds_requested']*27
    VIDEO['audit_stream'](path/'concurrent-gadget-stream')
    if full:
        assert len(r['restarts'])==6 and len(r['signal_cycles'])==3
        for index in range(3):
            for name in ('start','restart'):
                VIDEO['audit_stream'](path/f'{name}-stream-{index}')
            VIDEO['audit_stream'](path/f'recovery-{index}')
            VIDEO['audit_no_signal']((path/f'no-signal-kvmd-{index}.log').read_text())
            before=(path/f'signal-pid-before-{index}.log').read_text().strip()
            after=(path/f'signal-pid-after-{index}.log').read_text().strip()
            assert before==after==r['signal_cycles'][index]['pid']
            assert r['signal_cycles'][index]['automatic']
    return r


def main(a):
    bridge=a.bridge;series=bridge/'series'
    reproducible=read(a.reproducibility);assert reproducible['result']=='passed'
    build_hashes={}
    for artifact in reproducible['builds']:
        assert len(artifact['builds'])==2
        assert artifact['builds'][0]['sha256']==artifact['builds'][1]['sha256']
        build_hashes[artifact['artifact']]=artifact['builds'][0]['sha256']
    pre=read(bridge/'qualification/preflight-pass.json');assert pre['result']=='passed'
    preboot=read(bridge/'qualification/preflight-boot.json')
    manifest=read(bridge/'runs'/preboot['run_id']/'rootfs-manifest.json')
    assert manifest['public_base_image']['sha256']==build_hashes['initramfs.cpio.gz']
    for artifact in ('rootfs.tar.gz','kvmd-web_4.213-1blikvm2_arm64.deb'):
        assert manifest['artifacts'][artifact]['sha256']==build_hashes[artifact]
    full=read(bridge/'qualification/preflight-hil.json')
    hil_gate(bridge/'runs'/full['run_id'],full=True)
    browser_gate(a.preflight_browser,lifecycle=True)
    ng_before=inventory_gate(bridge/'qualification/preflight-nginx-before.json')
    ng_after=inventory_gate(bridge/'qualification/preflight-nginx-after.json')
    hdmi_before=inventory_gate(bridge/'qualification/preflight-hdmi-before.json',True)
    last=inventory_gate(bridge/'qualification/preflight-inventory.json',True)
    assert ng_before['ustreamer']['pid']==ng_after['ustreamer']['pid']
    assert hdmi_before['ustreamer']['pid']!=ng_after['ustreamer']['pid']
    assert hdmi_before['ustreamer']['pid']==last['ustreamer']['pid']
    exposure_gate(bridge/'qualification/preflight-exposure.json')
    reboot=REBOOTS['audit'](series/'boots.jsonl',bridge/'runs',5)
    assert reboot['artifacts']['initramfs.cpio.gz']['sha256']==pre['image_sha256']
    rows=[]
    for index in range(1,6):
        boot=read(series/f'boot-{index}.json')
        hil=read(series/f'hil-{index}.json')
        h=hil_gate(bridge/'runs'/hil['run_id'])
        before=inventory_gate(series/f'startup-{index}.json')
        exposure_gate(series/f'exposure-{index}.json')
        after=inventory_gate(series/f'inventory-{index}.json')
        assert before['boot_id']==after['boot_id']==h['boot_id']==reboot['runs'][index-1]['boot_id']
        assert before['ustreamer']['pid']==after['ustreamer']['pid']
        assert h['boot_run']==boot['run_id']
        web=browser_gate(a.client/f'browser-{index}')
        rows.append({'index':index,'boot_id':h['boot_id'],'boot_run':boot['run_id'],
                     'hil_run':hil['run_id'],**web})
    assert len({x['tls_fingerprint'] for x in rows})==1
    assert read(series/'result.json')['result']=='passed'
    return {'result':'passed','milestone':'M8-B','clean_boots':5,'boots':rows,
            'image_sha256':pre['image_sha256'],'video_clients_qualified':1,
            'm8a':'frozen','m6':'deferred','lan_exposure':False,'kvmd_hid_msd_atx':False}


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for name in ('bridge','client','preflight-browser','reproducibility'):
        p.add_argument('--'+name,type=Path,required=True)
    print(json.dumps(main(p.parse_args()),indent=2))
