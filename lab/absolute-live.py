#!/usr/bin/env python3
"""Qualify a completed physical G2 reconnect after a transient early enumeration.

The earlier boot remains failed. This separate live run proves the final cable
transition from archived host kernel events and tests the currently bound device.
It never reboots, sets up, unbinds, or binds the gadget. Two full boots follow.
"""
import argparse
import datetime
import hashlib
import json
from pathlib import Path
import re
import runpy
import subprocess
import time

REPO = Path(__file__).resolve().parents[1]
LAB = runpy.run_path(str(REPO / 'lab/labctl'))
G2 = runpy.run_path(str(REPO / 'lab/absolutelab.py'))
G1 = G2['G1']


def reconnect_sequence(log, port, previous_number, current_number):
    pattern = re.compile(r'^(\S+) usb ' + re.escape(port) +
                         r': (USB disconnect, device number (\d+)|new high-speed USB device number (\d+) using xhci_hcd)$')
    events = []
    for line in log.splitlines():
        match = pattern.match(line)
        if match:
            events.append({'time': match[1], 'kind': 'remove' if match[3] else 'add',
                           'number': match[3] or match[4]})
    starts = [i for i, e in enumerate(events) if e['kind'] == 'remove' and e['number'] == previous_number]
    if len(starts) != 1:
        raise RuntimeError('missing or ambiguous original physical disconnect')
    events = events[starts[0]:]
    if len(events) < 2 or len(events) % 2:
        raise RuntimeError('incomplete physical reconnect sequence')
    for i, e in enumerate(events):
        if e['kind'] != ('remove' if i % 2 == 0 else 'add'):
            raise RuntimeError('unexpected disconnect/enumeration ordering')
        if i > 0 and i % 2 == 0 and e['number'] != events[i-1]['number']:
            raise RuntimeError('USB device-number continuity lost')
    if events[-1]['number'] != current_number:
        raise RuntimeError('current device does not match final reconnect')
    start, end = [datetime.datetime.fromisoformat(e['time'].replace(',', '.')) for e in events[-2:]]
    interval = (end-start).total_seconds()
    if interval < 2:
        raise RuntimeError('final physical disconnect interval shorter than two seconds')
    return {'passed': True, 'events': events, 'final_disconnected_seconds': interval,
            'before': previous_number, 'after': current_number, 'repeated_this_boot': False,
            'qualified_live_after_prior_boot': True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--interrupted-run', required=True, type=Path)
    parser.add_argument('--device', type=Path, default=Path('/dev/serial/by-id/usb-1a86_USB_Serial-if00-port0'))
    args = parser.parse_args()
    prior = json.loads((args.interrupted_run/'test-results.json').read_text())
    meta = json.loads((args.interrupted_run/'metadata.json').read_text())
    if (prior.get('stage') != 'hid_reconnected_input' or prior.get('result') != 'failed'
            or prior.get('hid', {}).get('slice') != 'G2'
            or not prior['hid'].get('physical_reconnect', {}).get('passed')
            or not prior['hid'].get('unbind_rebind', {}).get('passed')):
        raise RuntimeError('requires an interrupted G2 post-reconnect run with recorded physical transition')
    recorder = LAB['RunRecorder']('g2-live-post-reconnect', REPO/'out/runs')
    recorder.metadata['artifacts'] = meta['artifacts']
    recorder.metadata['running_boot_evidence'] = prior['run_id']
    recorder.metadata['live_runner_sha256'] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    result = {'result': 'failed', 'stage': 'g2_live_post_reconnect_and_uvc', 'hid': {'slice': 'G2'}}
    monitor = G1['HostMonitor'](recorder)
    try:
        for name, digest in meta['automation_sha256'].items():
            if hashlib.sha256((REPO/name).read_bytes()).hexdigest() != digest:
                raise RuntimeError('tested automation changed since physical boot: ' + name)
        monitor.start()
        host_log = subprocess.check_output(['dmesg', '--time-format', 'iso'], text=True)
        recorder.save_text('host-physical-sequence.log', host_log)
        device = G2['wait_device'](True, 15)
        number = G2['read'](device/'devnum')
        physical = reconnect_sequence(host_log, device.name, prior['hid']['physical_reconnect']['before'], number)
        physical['evidence_run'] = prior['run_id']
        result['hid']['physical_reconnect'] = physical
        for role in ('keyboard_identity', 'mouse_identity'):
            if Path(prior['hid']['reconnected_enumeration'][role]['sysfs']).exists():
                raise RuntimeError('old evdev sysfs object survived final disconnect')
        # Require a quiet, stable final enumeration before any reports.
        time.sleep(2)
        if G2['read'](device/'devnum') != number:
            raise RuntimeError('device changed during stability interval')
        baseline = prior['hid']['enumeration']
        record = G2['details'](device)
        if (not record['passed'] or record['identity'] != baseline['identity']
                or record['usb_descriptors_sha256'] != baseline['usb_descriptors_sha256']):
            raise RuntimeError('final physical reconnect identity/USB descriptors differ')
        record['reports'] = G2['exact_descriptors'](device, recorder, 'live-reconnected')
        (recorder.path/'host-usb-live-reconnected.bin').write_bytes((device/'descriptors').read_bytes())
        result['hid']['enumeration'] = record
        G1['host_logs'](recorder, 'reconnected')
        with LAB['SerialConsole'](args.device, recorder) as console:
            def target(name, command):
                rc, output = LAB['capture_shell_command'](console, recorder, name+'.log', name.replace('-', '_'), command, 20)
                if rc:
                    raise RuntimeError(name + ': target rc=' + str(rc))
                return output
            target('live-quiet', 'echo N > /sys/module/printk/parameters/ignore_loglevel; dmesg -n 1')
            try:
                state = target('live-state-before', 'hid-absolute-mouse state')
                if 'state=configured' not in state or not G2['valid_functions'](state):
                    raise RuntimeError('unexpected target state after physical reconnect')
                for label in ('reconnected', 'concurrent'):
                    with G2['Capture'](device, recorder, 0) as keyboard, G2['Capture'](device, recorder, 1) as mouse:
                        result['hid']['capabilities'] = G2['mouse_caps'](mouse.fd)
                        target('live-prime-'+label, 'hid-keyboard report; hid-absolute-mouse report; sleep 0.2')
                        keyboard.neutral(); mouse.neutral()
                        command = G1['modifier_command']() + ' && ' + G2['mouse_command']()
                        try:
                            if label == 'concurrent':
                                result['uvc'] = LAB['run_uvc_test'](console, recorder, concurrent_hid=True, hid_report_command=command)
                            else:
                                target('live-reports-'+label, command)
                        finally:
                            target('live-release-'+label, 'hid-keyboard report; hid-absolute-mouse report; sleep 0.2')
                        result['hid'][label+'_input'] = {'keyboard': keyboard.verify(label+'-keyboard'),
                                                       'absolute_mouse': mouse.verify(label+'-mouse')}
                if result['uvc']['result'] != 'passed' or int(result['uvc']['capture_summary']['startup_error_frames']):
                    raise RuntimeError('concurrent UVC failed or had startup errors')
                target('live-quiet-after', 'echo N > /sys/module/printk/parameters/ignore_loglevel; dmesg -n 1')
                final = target('live-final-state', 'dmesg; hid-absolute-mouse state')
                if 'state=configured' not in final or not G2['valid_functions'](final):
                    raise RuntimeError('target configuration lost')
                if G2['read'](device/'devnum') != number or not G2['details'](device)['passed']:
                    raise RuntimeError('host device changed during live qualification')
                G2['exact_descriptors'](device, recorder, 'live-final')
                monitor.stop()
                # Restrict old host messages to the recorded physical-test window.
                start = next(i for i, line in enumerate(host_log.splitlines())
                             if physical['events'][0]['time'] in line)
                errors = (G1['usb_errors'](final) + G1['usb_errors']('\n'.join(host_log.splitlines()[start:]))
                          + G1['usb_errors'](G2['read'](recorder.path/'host-kernel-live.log')))
                result['hid']['usb_errors'] = {'passed': not errors, 'matching_lines': errors}
                if errors:
                    raise RuntimeError('USB errors observed: ' + str(errors))
                G1['host_logs'](recorder, 'after')
                result['result'] = 'passed'
            finally:
                target('live-final-collection', 'dmesg; hid-absolute-mouse state')
                target('live-restore', 'dmesg -n 8; echo Y > /sys/module/printk/parameters/ignore_loglevel')
    except Exception as error:
        result.update(result='failed', error=str(error))
    finally:
        monitor.stop()
        print(json.dumps(recorder.finish(result), indent=2), flush=True)


if __name__ == '__main__':
    main()
