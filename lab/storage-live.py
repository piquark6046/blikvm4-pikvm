#!/usr/bin/env python3
"""Qualify a completed physical G4 reconnect after an interrupted concurrent capture.

The earlier boot remains failed. This separate live run proves the final cable
transition from archived host kernel events and tests the currently bound device.
It never reboots, sets up, unbinds, or binds the gadget. Two full boots follow.
"""
import argparse
import ast
import datetime
import hashlib
import json
from pathlib import Path
import re
import runpy
import subprocess
import time
import threading
from concurrent.futures import ThreadPoolExecutor

REPO = Path(__file__).resolve().parents[1]
LAB = runpy.run_path(str(REPO / 'lab/labctl'))
G4 = runpy.run_path(str(REPO / 'lab/storagelab.py'))
G1 = G4['G1']


reconnect_sequence = runpy.run_path(str(REPO / 'lab/absolute-live.py'))['reconnect_sequence']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--interrupted-run', required=True, type=Path)
    parser.add_argument('--device', type=Path, default=Path('/dev/serial/by-id/usb-1a86_USB_Serial-if00-port0'))
    args = parser.parse_args()
    prior = json.loads((args.interrupted_run/'test-results.json').read_text())
    meta = json.loads((args.interrupted_run/'metadata.json').read_text())
    if (prior.get('stage') != 'hid_concurrent_uvc' or prior.get('result') != 'failed'
            or prior.get('hid', {}).get('slice') != 'G4'
            or not prior['hid'].get('physical_reconnect', {}).get('passed')
            or not prior['hid'].get('unbind_rebind', {}).get('passed')
            or not prior['hid'].get('physical_reconnect', {}).get('old_storage_removed')
            or not prior['hid'].get('storage', {}).get('reconnected', {}).get('passed')
            or not all(prior['hid'].get('reconnected_input', {}).get(role, {}).get('passed')
                       for role in ('keyboard', 'absolute_mouse', 'relative_mouse'))):
        raise RuntimeError('requires an interrupted G4 post-reconnect run with recorded physical transition')
    recorder = LAB['RunRecorder']('g4-live-post-reconnect', REPO/'out/runs')
    recorder.metadata['artifacts'] = meta['artifacts']
    recorder.metadata['running_boot_evidence'] = prior['run_id']
    recorder.metadata['live_runner_sha256'] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    result = {'result': 'failed', 'stage': 'g4_live_post_reconnect_and_uvc', 'hid': {'slice': 'G4'}}
    monitor = G1['HostMonitor'](recorder)
    try:
        for name, digest in meta['automation_sha256'].items():
            current = (REPO/name).read_bytes()
            if hashlib.sha256(current).hexdigest() != digest:
                # Only the reviewed import-shadowing fix may differ from this physical run.
                archived = (args.interrupted_run/'physical-storagelab.py').read_bytes()
                if name != 'lab/storagelab.py' or hashlib.sha256(archived).hexdigest() != digest:
                    raise RuntimeError('unverified physical verifier source')
                restored = current.decode().replace('from concurrent.futures import ThreadPoolExecutor', 'import concurrent.futures').replace('with ThreadPoolExecutor(', 'with concurrent.futures.ThreadPoolExecutor(')
                def retained_ast(source):
                    tree=ast.parse(source)
                    tree.body=[n for n in tree.body if not (isinstance(n,ast.FunctionDef) and n.name in ('storage_test','storage_during_uvc','unexpected_resets'))]
                    return ast.dump(tree,include_attributes=False)
                if retained_ast(restored) != retained_ast(archived.decode()):
                    raise RuntimeError('physical or HID verifier behavior changed')
                recorder.metadata['verifier_fix'] = {'source':name, 'before':digest, 'after':hashlib.sha256(current).hexdigest(), 'change':'fix concurrency import; direct reads only during UVC; robust mount cleanup; physical and HID verifier AST unchanged'}
        monitor.start()
        host_log = subprocess.check_output(['dmesg', '--time-format', 'iso'], text=True)
        recorder.save_text('host-physical-sequence.log', host_log)
        device = G4['wait_device'](True, 15)
        number = G4['read'](device/'devnum')
        physical = reconnect_sequence(host_log, device.name, prior['hid']['physical_reconnect']['before'], number)
        physical['evidence_run'] = prior['run_id']
        result['hid']['physical_reconnect'] = physical
        if number != prior['hid']['physical_reconnect']['after']:
            raise RuntimeError('device changed after the qualified physical transition')
        for index, role in enumerate(G4['IDENTITY_KEYS']):
            if Path(prior['hid']['unbind_rebind']['enumeration'][role]['sysfs']).exists():
                raise RuntimeError('pre-disconnect input survived physical removal')
            current = G4['Capture'](device, recorder, index).identity
            if current != prior['hid']['reconnected_enumeration'][role]:
                raise RuntimeError('current input differs from recorded reconnected device')
        old_storage = json.loads((args.interrupted_run/'storage-absent-physical.json').read_text())
        if not old_storage.get('passed') or old_storage['identity'] != prior['hid']['unbind_rebind']['enumeration']['storage_identity']:
            raise RuntimeError('missing original storage removal evidence')
        if G4['block_identity'](device) != prior['hid']['reconnected_enumeration']['storage_identity']:
            raise RuntimeError('SCSI identity changed since physical reconnect')
        physical['old_storage_removed'] = True
        # Require a quiet, stable final enumeration before any reports.
        time.sleep(2)
        if G4['read'](device/'devnum') != number:
            raise RuntimeError('device changed during stability interval')
        baseline = prior['hid']['enumeration']
        record = G4['details'](device)
        if (not record['passed'] or record['identity'] != baseline['identity']
                or record['usb_descriptors_sha256'] != baseline['usb_descriptors_sha256']):
            raise RuntimeError('final physical reconnect identity/USB descriptors differ')
        record['reports'] = G4['exact_descriptors'](device, recorder, 'live-reconnected')
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
                state = target('live-state-before', 'gadget-storage state')
                if G4['EXPECTED']['sha256']+'  /usr/share/g4-storage.img' not in state:
                    raise RuntimeError('backing hash mismatch before live checks')
                if 'state=configured' not in state or not G4['valid_functions'](state):
                    raise RuntimeError('unexpected target state after physical reconnect')
                mapping = G4['parse_mapping'](target('live-mapping', G4['mapping_command'](True)), True)
                if mapping != prior['hid']['function_mapping']:
                    raise RuntimeError('function mapping changed')
                result['hid']['function_mapping'] = mapping
                for label in ('reconnected', 'concurrent'):
                    with G4['Capture'](device, recorder, 0) as keyboard, G4['Capture'](device, recorder, 1) as mouse, G4['Capture'](device, recorder, 2) as relative:
                        result['hid']['capabilities'] = G4['mouse_caps'](mouse.fd)
                        result['hid']['relative_capabilities'] = G4['relative_caps'](relative.fd)
                        target('live-prime-'+label, 'hid-keyboard report; hid-absolute-mouse report; hid-relative-mouse report; sleep 0.2')
                        keyboard.neutral(); mouse.neutral(); relative.neutral()
                        command = G1['modifier_command']() + ' && ' + G4['mouse_command']() + ' && ' + G4['relative_command']()
                        try:
                            if label == 'concurrent':
                                for name, staged in G4['concurrent_setup_commands']():
                                    target('live-script-' + name, staged)
                                command = G4['concurrent_command']()
                                stopped = threading.Event()
                                with ThreadPoolExecutor(max_workers=1) as pool:
                                    future = pool.submit(G4['storage_during_uvc'], device, recorder, stopped)
                                    try:
                                        result['uvc'] = LAB['run_uvc_test'](console, recorder, concurrent_hid=True, hid_report_command=command)
                                    finally:
                                        stopped.set()
                                    result['hid'].setdefault('storage', {})[label] = future.result()
                            else:
                                result['hid'].setdefault('storage', {})[label] = G4['storage_test'](device, recorder, label)
                                target('live-reports-'+label, command)
                        finally:
                            target('live-release-'+label, 'hid-keyboard report; hid-absolute-mouse report; hid-relative-mouse report; sleep 0.2')
                        result['hid'][label+'_input'] = {'keyboard': keyboard.verify(label+'-keyboard'),
                                                       'absolute_mouse': mouse.verify(label+'-mouse'),
                                                       'relative_mouse': relative.verify(label+'-relative')}
                if result['uvc']['result'] != 'passed' or int(result['uvc']['capture_summary']['startup_error_frames']):
                    raise RuntimeError('concurrent UVC failed or had startup errors')
                target('live-quiet-after', 'echo N > /sys/module/printk/parameters/ignore_loglevel; dmesg -n 1')
                final = target('live-final-state', 'dmesg; gadget-storage state')
                if G4['EXPECTED']['sha256']+'  /usr/share/g4-storage.img' not in final:
                    raise RuntimeError('backing hash mismatch after live checks')
                if 'state=configured' not in final or not G4['valid_functions'](final):
                    raise RuntimeError('target configuration lost')
                if G4['read'](device/'devnum') != number or not G4['details'](device)['passed']:
                    raise RuntimeError('host device changed during live qualification')
                G4['exact_descriptors'](device, recorder, 'live-final')
                final_mapping = G4['parse_mapping'](target('live-final-mapping', G4['mapping_command'](True)), True)
                if final_mapping != mapping:
                    raise RuntimeError('final function mapping changed')
                result['hid']['final_state'] = {'passed': True, 'bound': True, 'mapping': final_mapping}
                monitor.stop()
                # Restrict old host messages to the recorded physical-test window.
                start = next(i for i, line in enumerate(host_log.splitlines())
                             if physical['events'][0]['time'] in line)
                errors = (G1['usb_errors'](final) + G1['usb_errors']('\n'.join(host_log.splitlines()[start:]))
                          + G1['usb_errors'](G4['read'](recorder.path/'host-kernel-live.log')))
                storage_logs = '\n'.join(host_log.splitlines()[start:])+'\n'+G4['read'](recorder.path/'host-kernel-live.log')
                errors += [line for line in storage_logs.splitlines() if re.search(r'(?:scsi|sd |usb-storage).*(?:I/O error|timed out|reset|abort|offline)',line,re.I) and 'Power-on or device reset occurred' not in line]
                errors += G4['unexpected_resets'](storage_logs)
                result['hid']['usb_errors'] = {'passed': not errors, 'matching_lines': errors}
                if errors:
                    raise RuntimeError('USB errors observed: ' + str(errors))
                G1['host_logs'](recorder, 'after')
                result['result'] = 'passed'
            finally:
                target('live-final-collection', 'dmesg; gadget-storage state')
                target('live-restore', 'dmesg -n 8; echo Y > /sys/module/printk/parameters/ignore_loglevel')
    except Exception as error:
        result.update(result='failed', error=str(error))
    finally:
        monitor.stop()
        print(json.dumps(recorder.finish(result), indent=2), flush=True)


if __name__ == '__main__':
    main()
