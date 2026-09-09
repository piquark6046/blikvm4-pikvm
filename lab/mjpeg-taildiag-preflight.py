#!/usr/bin/env python3
"""Bounded diagnostic-only preflight. Never begins observation 03 or repairs services."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import runpy
import subprocess
import sys
import tarfile
import time

HERE=Path(__file__).resolve().parent
DIAG='/var/lib/ustreamer-taildiag'

def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True)
    p.add_argument('--boot-result',type=Path,required=True);p.add_argument('--binary-sha256',required=True)
    p.add_argument('--seconds',type=int,default=300);a=p.parse_args()
    assert a.seconds>=240
    os.umask(0o077);out=a.output.resolve();out.mkdir(exist_ok=False)
    known=Path(json.loads(a.boot_result.read_text())['run_directory'])/'known_hosts'
    ssh=['ssh','-i','/home/user/.local/share/blikvm-m7/id_ed25519','-o','BatchMode=yes',
         '-o','StrictHostKeyChecking=yes','-o','UserKnownHostsFile='+str(known),
         '-o','ConnectTimeout=10','blikvm@192.168.88.2']
    result={'result':'failed','qualification':'NOT_RUN','long_observation_started':False,
            'thresholds':{'fps_per_client':27,'gap_seconds':3,'rss_delta_bytes':64*1024*1024,'cpu_additional_percentage_points':25}}
    process=None;samples=[]
    def run(label,cmd,stdin=None,timeout=60):
        r=subprocess.run(cmd,input=stdin,capture_output=True,timeout=timeout)
        (out/(label+'.stdout')).write_bytes(r.stdout);(out/(label+'.stderr')).write_bytes(r.stderr)
        assert r.returncode==0,label+' failed with rc '+str(r.returncode)
        return r.stdout
    def sample(label,flush=False):
        text=(HERE/'mjpeg-taildiag-runtime.py').read_text()
        # Suppress the CLI entrypoint and invoke explicitly, including immediate flush when requested.
        script="__name__='taildiag_sample'\n"+text+f'\nprint(json.dumps(sample({flush!r})))\n'
        value=json.loads(run(label,ssh+['sudo -n python3 -'],script.encode()))
        u=value['ustreamer'];assert u['executable_sha256']==a.binary_sha256
        assert u['diagnostic_directory']==DIAG and u['session']['pid']==u['pid']
        assert value['video_mode']['rc']==0
        mode=value['video_mode']['stdout']
        assert all(x in mode for x in ("'MJPG'",'1920/1080','30.000 (30/1)'))
        assert value['failed_units']['rc']==0 and not value['failed_units']['stdout'].strip()
        assert set(value['udc'].values())=={'configured'}
        samples.append(value);return value
    try:
        for n in ('lsusb','lsusb-tree','dmesg'):
            run('host-before-'+n,['lsusb','-t'] if n=='lsusb-tree' else [n])
        # Original observer and runner are unchanged; two clients are authenticated over SSH and HTTPS.
        with (out/'observer.stdout').open('wb') as o,(out/'observer.stderr').open('wb') as e:
            process=subprocess.Popen([sys.executable,str(HERE/'mjpeg-observe-run.py'),'--output',str(out/'observation'),
                '--known-hosts',str(known),'--private-dir',str(Path('private').resolve()),'--seconds',str(a.seconds)],stdout=o,stderr=e)
        deadline=time.monotonic()+45
        while not (out/'observation/clients/direct/frames.jsonl').exists() or not (out/'observation/clients/https/frames.jsonl').exists():
            assert process.poll() is None,'observer runner exited during startup'
            assert time.monotonic()<deadline,'observer startup timeout';time.sleep(.25)
        time.sleep(3);sample('diagnostic-start',True)
        run('hid-regression',[sys.executable,str(HERE/'hid-api-hil.py'),'--private-dir',str(Path('private').resolve()),'--output',str(out/'hid-regression')],timeout=120)
        run('msd-regression',[sys.executable,str(HERE/'msd-hil.py'),'--output',str(out/'msd-regression'),'--boot-result',str(a.boot_result.resolve())],timeout=120)
        i=0
        while process.poll() is None:
            sample(f'diagnostic-{i:03d}');i+=1
            try:process.wait(timeout=20)
            except subprocess.TimeoutExpired:pass
        assert process.returncode==0,'observer runner failed'
        sample('diagnostic-end',True)
        replay=runpy.run_path(str(HERE/'mjpeg-observe-compare.py'))['replay'](out/'observation/clients')
        (out/'replay.json').write_text(json.dumps(replay,indent=2)+'\n')
        for n,c in replay['clients'].items():
            r=json.loads((out/'observation/clients'/n/'result.json').read_text())
            assert r['result']=='observation_complete' and not r['gate_violations']
            assert c['anomalies']==0 and c['fps_gate_met'] and not c['motion_failure_windows'] and c['max_gap']<=3
        assert not replay['payload_mismatches']
        identity={(s['boot_id'],s['ustreamer']['pid'],s['ustreamer']['start_ticks']) for s in samples};assert len(identity)==1
        first,last=samples[0],samples[-1]
        cpu=(last['ustreamer']['ticks']-first['ustreamer']['ticks'])/(last['monotonic']-first['monotonic'])*100/last['ustreamer']['clock_ticks']
        rss=max(s['ustreamer']['rss_bytes'] for s in samples)
        result['resources']={'cpu_percent_one_core':cpu,'maximum_rss_bytes':rss,'baseline_cpu_percent':3.755,'baseline_rss_bytes':30760960}
        assert cpu<=3.755+25 and rss<=30760960+64*1024*1024,'diagnostic resource overhead exceeds bounded preflight limit'
        result['stream_and_regression_gates']='passed'
    except Exception as ex:
        result['error']=str(ex)
    finally:
        if process is not None and process.poll() is None:
            # Allow the already bounded observer to finalize evidence naturally even on a preflight assertion.
            try:process.wait(timeout=a.seconds+40)
            except subprocess.TimeoutExpired:
                process.terminate();process.wait(timeout=10)
                result['observer_forced_stop']=True
        try:
            # Preserve recent records and let the writer drain before normal service shutdown.
            try:sample('final-flush',True)
            except Exception as ex:result['flush_error']=str(ex)
            run('target-before-stop-dmesg',ssh+['sudo -n dmesg'])
            run('controlled-stop',ssh+['sudo -n systemctl stop kvmd.service'],timeout=40)
            # StateDirectory lives on the RAM root and survives RuntimeDirectory cleanup.
            data=run('target-diagnostics-tar',ssh+['sudo -n tar -C '+DIAG+' -cf - .'],timeout=45)
            archive=out/'target-diagnostics.tar';archive.write_bytes(data)
            diag=out/'target-diagnostics';diag.mkdir()
            with tarfile.open(archive) as t:t.extractall(diag,filter='data')
            summary=json.loads((diag/'summary.json').read_text());result['diagnostic_summary']=summary
            acks=[v['ustreamer']['flush_acknowledgement'] for v in samples if v['flush_requested']]
            assert 'flush_error' not in result
            assert summary['snapshots']==summary['snapshots_written']==len(acks)==3
            assert summary['write_errors']==0
            assert len(list(diag.glob('flush-*.json')))==len(acks)
            for ack in acks:
                disk=json.loads((diag/('flush-'+ack['nonce']+'.json')).read_text())
                assert disk['nonce']==ack['nonce'] and disk['result']=='passed'
                assert json.loads((diag/disk['snapshot']).read_text())['nonce']==ack['nonce']
            for s in summary['stages']:
                assert s['accepted']==s['written'] and s['suppressed']==0 and s['oversized_or_invalid_length']==0
                assert s['suspicious_seen']==s['accepted']+s['suppressed']
                assert s['accepted']==s['raw_written']+s['raw_skipped']
                assert s['metadata_misses']==0 and s['inspected']>0
                events=[json.loads(p.read_text()) for p in diag.glob(s['stage']+'-*.json')]
                assert len(events)==s['written']
                assert sum(e['payload_file'] is not None for e in events)==s['raw_written']
                assert len(list(diag.glob(s['stage']+'-*.bin')))==s['raw_written']
                for event in events:
                    assert event['metadata_suppressed'] is False
                    j=event['jpeg'];b=event['boundary']
                    assert len(bytes.fromhex(j['trailing_hex']))==j['trailing_length']
                    assert j['bytesused']==b['bytesused'] and j['sha256']==b['sha256']
                    if event['payload_file']:
                        payload=(diag/event['payload_file']).read_bytes()
                        assert len(payload)==j['bytesused'] and hashlib.sha256(payload).hexdigest()==j['sha256']
                        assert payload[j['final_eoi_offset']+2:].hex()==j['trailing_hex']
                        assert hashlib.sha256(payload[:j['final_eoi_offset']+2]).hexdigest()==j['through_final_eoi_sha256']
            assert not list(diag.glob('*.partial')) and not (diag/'flush.request').exists()
            for f in diag.glob('*.json'):json.loads(f.read_text())
            if result.get('stream_and_regression_gates')=='passed' and 'error' not in result:
                result['result']='pending_independent_vm_review'
        except Exception as ex:result['drain_or_archive_error']=str(ex)
        for n in ('lsusb','lsusb-tree','dmesg'):
            try:run('host-after-'+n,['lsusb','-t'] if n=='lsusb-tree' else [n])
            except Exception as ex:result['inventory_error']=str(ex);result['result']='failed'
        (out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result));return result['result']=='pending_independent_vm_review'

if __name__=='__main__':raise SystemExit(not main())
