#!/usr/bin/env python3
"""Offline M8-C gate: replay raw frame evidence and independent boot results."""
import argparse
import hashlib
import json
from pathlib import Path
import runpy
import ssl


def load(path):return json.loads(path.read_text())


def stream(root,seconds=120):
    r=load(root/'result.json');assert r['result']=='passed'
    records=[json.loads(s) for s in (root/'frames.jsonl').read_text().splitlines()]
    assert r['seconds_requested']>=seconds and r['elapsed']>=seconds
    assert len(records)==r['frames'] and len(records)>=seconds*27
    fps=len(records)/r['elapsed'];assert fps>=27
    assert all(x['bytes']>4 and len(x['sha256'])==64 for x in records)
    assert sum(x['bytes'] for x in records)==r['bytes']
    unique=len({x['sha256'] for x in records});assert unique==r['unique_hashes']
    stamps=[0]+[x['t'] for x in records]+[float(seconds)]
    gaps=[b-a for a,b in zip(stamps,stamps[1:])]
    assert all(x>=0 for x in gaps[:-1]) and max(gaps)<=3
    for i in range(seconds//5):
        assert len({x['sha256'] for x in records if i*5<=x['t']<(i+1)*5})>=2
    return {'frames':len(records),'fps':fps,'bytes':r['bytes'],'unique_hashes':unique,
            'transitions':sum(a['sha256']!=b['sha256'] for a,b in zip(records,records[1:])),
            'max_gap':max(gaps)}


def browser(root,fingerprint,lifecycle=False):
    r=load(root/'result.json');assert r['result']=='passed'
    assert r['tls']['verified'] and r['tls']['fingerprint256'].replace(':','').lower()==fingerprint
    assert r['browser']['wrong_name_rejected'] and r['browser']['logout']
    assert not r['browser']['errors'] and all(x['status']<400 for x in r['browser']['assets'])
    for label in ('initial','reload','after_rate_gate'):
        assert len(set(r['browser'][label]['hashes']))>=4
    if lifecycle:
        assert r['browser']['lifecycle']
        for label in ('nginx_restart','kvmd_restart_reauthenticated','hdmi_recovered'):
            assert len(set(r['browser'][label]['hashes']))>=4
        assert len(set(r['browser']['hdmi_loss']['hashes']))==1
    source=(root/'runner.mjs').read_text()
    assert 'ignoreHTTPSErrors:true' not in source and '--ignore-certificate-errors' not in source
    assert 'ignoreHTTPSErrors:false' in source
    assert hashlib.sha256(source.encode()).hexdigest()==r['automation_sha256']
    assert r['rate_load']['tunnel'] is False
    return stream(root/'stream')


def access(root,fingerprint):
    r=load(root/'result.json');assert r['result']=='passed' and r['tunnel'] is False
    negatives=[x for x in r['tls'] if x.get('rejected')]
    assert {x['negative'] for x in negatives}=={'wrong-name','untrusted'}
    good=[x for x in r['tls'] if x.get('verified')]
    assert {(x['identity'],x['version']) for x in good}=={
        (name,version) for name in ('blikvm-v4.lab','192.168.88.2') for version in ('TLSv1.2','TLSv1.3')}
    assert all(x['sha256']==fingerprint for x in good)
    assert any(x['source']=='192.168.88.99' and x['port']==443 and x['errno']!=0 for x in r['probes'])


def capacity(root,expected=2):
    r=load(root/'result.json');assert r['result']=='passed' and r['seconds']>=120
    assert r['client_count']==expected
    for name,digest in r['automation_sha256'].items():
        assert hashlib.sha256((root/('source-'+name)).read_bytes()).hexdigest()==digest
    summarize=runpy.run_path(str(Path(__file__).with_name('lan-resource-summary.py')))['summarize']
    resources=summarize(root/'target-resources.jsonl')
    assert sum(v['clients']==expected for v in resources['streamer_client_states'])>=50
    assert len(set(r['measurement_processes']))==r['client_count']
    assert len(r['reconnect'])==r['client_count']
    assert all(x['stream_result']=='passed' and x['unique_hashes']>1 for x in r['reconnect'])
    return [stream(root/f'client-{i}') for i in range(r['client_count'])]


def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True)
    p.add_argument('--certificate',type=Path,required=True);a=p.parse_args();root=a.root
    fingerprint=hashlib.sha256(ssl.PEM_cert_to_DER_cert(a.certificate.read_text())).hexdigest()
    q=root/'qualification';series=root/'series'
    assert load(q/'final-hil.json')['result']=='passed'
    pre=load(q/'final-session/result.json');assert pre['result']=='passed'
    preflight=browser(q/'final-session/browser',fingerprint,True)
    access(q/'final-access',fingerprint)
    single=capacity(q/'single-final',1)
    assert len(pre['capacity'])>=3
    trials=[capacity(q/'final-session'/x['path']) for x in pre['capacity']]
    s=load(series/'result.json');assert s['result']=='passed' and len(s['completed'])==5
    assert s['two_client_gate'], 'this gate expects an accepted two-client slice'
    assert load(series/'five-boot-gate.json')['result']=='passed'
    boots=[];images=set();ids=set()
    for i in range(1,6):
        b=load(series/f'boot-{i}.json');h=load(series/f'hil-{i}.json')
        assert b['result']==h['result']=='passed'
        assert b==load(root/'runs'/b['run_id']/'test-results.json')
        assert h==load(root/'runs'/h['run_id']/'test-results.json')
        meta=load(root/'runs'/b['run_id']/'metadata.json')
        images.add(meta['artifacts']['initramfs.cpio.gz']['sha256'])
        startup=load(series/f'startup-{i}.json');assert startup['result']=='passed'
        ids.add(startup['boot_id'])
        access(series/f'access-{i}',fingerprint)
        session=series/f'session-{i}';v=load(session/'result.json');assert v['result']=='passed'
        for name in ('inventory-before','inventory-after'):
            assert load(session/(name+'.log'))['result']=='passed'
        boots.append({'index':i,'boot_id':startup['boot_id'],'boot_run':b['run_id'],'hil_run':h['run_id'],
                      'single':browser(session/'browser',fingerprint),'two':capacity(session/'two-capacity-1')})
    assert len(ids)==5 and images=={'b9617300a246a20aa7d58d74a878f586bc03abeabed83bd66a16c1e48fc7d93e'}
    return {'result':'passed','milestone':'M8-C','certificate_sha256':fingerprint,
            'image_sha256':next(iter(images)),'qualified_clients':2,'preflight_single':preflight,
            'single_resource_trial':single,'two_client_trials':trials,'boots':boots}


if __name__=='__main__':print(json.dumps(main(),indent=2))
