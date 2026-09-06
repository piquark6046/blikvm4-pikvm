#!/usr/bin/env python3
"""Independently audit multiple final-payload uStreamer HIL results."""
import argparse
import json
from pathlib import Path
import re



def audit_stream(directory):
    result=json.loads((directory/'result.json').read_text())
    rows=[json.loads(line) for line in (directory/'frames.jsonl').read_text().splitlines()]
    seconds=result['seconds_requested']
    if result['result']!='passed' or result['elapsed']<seconds or len(rows)<seconds*5:
        raise ValueError('incomplete bounded stream')
    if result['frames']!=len(rows) or result['bytes']!=sum(r['bytes'] for r in rows):
        raise ValueError('frame/byte summary mismatch')
    if any(r['bytes']<4 or not re.fullmatch('[0-9a-f]{64}',r['sha256']) for r in rows):
        raise ValueError('invalid frame record')
    times=[0]+[r['t'] for r in rows]+[seconds]
    if any(b-a>3 or b<a for a,b in zip(times[:-2],times[1:-1])) or seconds-rows[-1]['t']>3:
        raise ValueError('stream gap or nonmonotonic frame time')
    transitions=sum(a['sha256']!=b['sha256'] for a,b in zip(rows,rows[1:]))
    if result['transitions']!=transitions: raise ValueError('transition summary mismatch')
    if result['unique_hashes']!=len({r['sha256'] for r in rows}):
        raise ValueError('hash summary mismatch')
    for window in range(int(seconds//5)):
        if len({r['sha256'] for r in rows if window*5<=r['t']<(window+1)*5})<2:
            raise ValueError('frozen five-second interval')
    return {k:result[k] for k in ('seconds_requested','elapsed','frames','bytes','unique_hashes','transitions')}


def audit_run(path):
    result=json.loads((path/'test-results.json').read_text())
    if result['result']!='passed' or result['stage']!='ustreamer_qualification':
        raise ValueError('HIL did not pass')
    if len(result['restarts'])!=6 or len(result['signal_cycles'])!=3:
        raise ValueError('missing restart/signal repetitions')
    if not all(c['automatic'] and int(c['pid'])>0 and c['recovery']['result']=='passed' for c in result['signal_cycles']):
        raise ValueError('nonautomatic signal recovery')
    if not result['storage']['passed'] or not result['concurrent_storage']['passed']:
        raise ValueError('storage regression')
    if set(result['hid'])!={'keyboard','absolute','relative'} or not all(v['passed'] for v in result['hid'].values()):
        raise ValueError('HID regression')
    if result['usb_errors'] or result.get('uart_errors') or result.get('cleanup_error'):
        raise ValueError('hardware/cleanup errors')
    streams={name:audit_stream(path/name) for name in ['sustained','concurrent-gadget-stream']+
             [f'{kind}-stream-{i}' for i in range(3) for kind in ('start','restart')]+[f'recovery-{i}' for i in range(3)]}
    if streams['sustained']['frames'] < streams['sustained']['seconds_requested']*27:
        raise ValueError('sustained delivery below 27 fps')
    mode=(path/'negotiated-after.log').read_text()
    if not all(s in mode for s in ('1920/1080',"'MJPG'",'30.000')):
        raise ValueError('negotiated mode mismatch')
    props=(path/'video-properties.log').read_text().splitlines()
    for expected in ('ID_VENDOR_ID=345f','ID_MODEL_ID=2131','ID_SERIAL_SHORT=29404080','ID_V4L_CAPABILITIES=:capture:'):
        if expected not in props: raise ValueError('wrong video identity')
    for i in range(3):
        raw=json.loads((path/f'hdmi-off-state-{i}.log').read_text())['stdout']
        # Select the only connected HDMI-A-2 section, not another output's DPMS.
        section=re.split(r'\n\d+\t',raw)
        matches=[part for part in section if 'HDMI-A-2' in part]
        if len(matches)!=1 or not re.search(r'\d+ DPMS:\n\s*flags:[^\n]*\n\s*enums:[^\n]*\n\s*value: 3(?:\n|$)',matches[0]):
            raise ValueError('missing HDMI DPMS Off evidence')
        before=(path/f'signal-pid-before-{i}.log').read_text().strip()
        after=(path/f'signal-pid-after-{i}.log').read_text().strip()
        if before!=after or before!=result['signal_cycles'][i]['pid']:
            raise ValueError('PID changed during signal recovery')
    journal=(path/'final-journal.log').read_text()
    errors=[line for line in journal.splitlines() if '-- ERROR' in line]
    if errors: raise ValueError('uStreamer errors: '+str(errors))
    resource_rows=[]
    for line in (path/'resources.log').read_text().splitlines():
        fields=line.split()
        if len(fields)==8 and fields[0].isdigit() and fields[2] in ('ustreamer','ustream+'):
            resource_rows.append(fields)
    if len(resource_rows)<2 or any(int(row[6])<=0 for row in resource_rows):
        raise ValueError('missing valid RSS samples')
    rss=[int(row[6]) for row in resource_rows]
    cpu=[float(row[5]) for row in resource_rows]
    resources=dict(samples=len(rss),rss_kib_min=min(rss),rss_kib_max=max(rss),
                   process_lifetime_cpu_percent_min=min(cpu),process_lifetime_cpu_percent_max=max(cpu))
    return dict(run_id=result['run_id'],boot_id=result['boot_id'],boot_run=result['boot_run'],
                streams=streams,resources=resources,ustreamer_errors=[],
                metadata=json.loads((path/'metadata.json').read_text()))


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('runs',nargs='+',type=Path)
    a=p.parse_args()
    if len(a.runs)<2: p.error('at least two final-image HIL runs required')
    records=[audit_run(path) for path in a.runs]
    if len({r['boot_id'] for r in records})!=len(records): raise ValueError('reused boot')
    hashes=[r['metadata']['artifacts']['initramfs.cpio.gz']['sha256'] for r in records]
    if len(set(hashes))!=1: raise ValueError('different rootfs payloads')
    for record in records: del record['metadata']
    print(json.dumps(dict(result='passed',rootfs_sha256=hashes[0],runs=records),indent=2))
