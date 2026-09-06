#!/usr/bin/env python3
"""Audit the complete two-full-plus-three-smoke sequence; no build acceptance implied."""
import argparse
import json
from pathlib import Path
import runpy

HERE=Path(__file__).resolve().parent
AUDIT=runpy.run_path(str(HERE/'kvmd-gate.py'))
p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);a=p.parse_args()
q=a.root/'qualification'
boots=[json.loads(line) for line in (q/'boots.jsonl').read_text().splitlines()]
hils=[json.loads(line) for line in (q/'hils.jsonl').read_text().splitlines()]
assert len(boots)==len(hils)==5
assert len({h['boot_id'] for h in hils})==5
assert json.loads((q/'full-hil-gate.json').read_text())['result']=='passed'
assert json.loads((q/'five-boot-gate.json').read_text())['result']=='passed'
records=[];hashes=set()
for i,(b,h) in enumerate(zip(boots,hils)):
    path=a.root/'runs'/h['run_id']
    assert b['result']==h['result']=='passed'
    assert h['boot_run']==b['run_id']
    assert h['stage']==('kvmd_video_qualification' if i<2 else 'kvmd_boot_smoke')
    if i<2: AUDIT['audit_run'](path)
    else: AUDIT['audit_api'](path,minimum=2)
    sustained=AUDIT['audit_stream'](path/'sustained')
    assert sustained['seconds_requested']>=120 and sustained['frames']>=sustained['seconds_requested']*27
    AUDIT['audit_stream'](path/'concurrent-gadget-stream')
    assert h['storage']['passed'] and h['concurrent_storage']['passed']
    assert set(h['hid'])=={'keyboard','absolute','relative'} and all(v['passed'] for v in h['hid'].values())
    assert not h['usb_errors'] and not h.get('uart_errors') and not h.get('cleanup_error')
    mode=(path/'negotiated-after.log').read_text()
    assert all(v in mode for v in ('1920/1080',"'MJPG'",'30.000 (30/1)'))
    identity=(path/'identity.log').read_text()
    assert 'e5a489c828299bc28de71789414312510198c6d7da63b2b18c300bef6313e71b' in identity
    final=(path/'final-service.log').read_text()
    assert 'User=kvmd' in final and 'Group=ustreamer' in final
    assert '/run/kvmd/api/kvmd.sock' in final and '/run/kvmd/ustreamer/ustreamer.sock' in final
    listeners=[l for l in final.splitlines() if l.startswith(('tcp ','udp '))]
    assert len(listeners)==1 and '192.168.88.2:22' in listeners[0],listeners
    journal=(path/'final-journal.log').read_text()
    assert 'ERROR' not in journal and 'Traceback' not in journal
    meta=json.loads((path/'metadata.json').read_text())
    hashes.add(meta['artifacts']['initramfs.cpio.gz']['sha256'])
    records.append(dict(boot_id=h['boot_id'],boot_run=b['run_id'],hil_run=h['run_id'],
                        kind='full' if i<2 else 'boot_smoke',sustained=sustained))
assert len(hashes)==1
print(json.dumps(dict(result='passed',rootfs_sha256=hashes.pop(),boots=records,
                     build_reproducibility='separate_required_gate'),indent=2))
