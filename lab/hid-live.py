#!/usr/bin/env python3
"""Qualify the bound keyboard after a separately monitored physical reconnect.

Does not reboot or configure a gadget. The referenced physical evidence must
match the current artifact set; complete boot qualification follows separately.
"""
import argparse
import json
from pathlib import Path
import runpy

REPO = Path(__file__).resolve().parents[1]
lab = runpy.run_path(str(REPO / 'lab/labctl'))
hid = runpy.run_path(str(REPO / 'lab/hidlab.py'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reconnect-evidence', required=True, type=Path)
    parser.add_argument('--device', default='/dev/serial/by-id/usb-1a86_USB_Serial-if00-port0', type=Path)
    args = parser.parse_args()
    recorder = lab['RunRecorder']('g1-live-report-uvc', REPO / 'out/runs')
    metadata = json.loads(args.reconnect_evidence.with_name('metadata.json').read_text())
    recorder.metadata['artifacts'] = metadata['artifacts']
    result = {'result': 'failed', 'stage': 'live-report-uvc', 'hid': {}}
    monitor = hid['HostMonitor'](recorder)
    try:
        result['hid']['physical_reconnect'] = hid['prior_reconnect'](args.reconnect_evidence, metadata['artifacts'])
        monitor.start()
        with lab['SerialConsole'](args.device, recorder) as console:
            def target(name, command):
                rc, text = lab['capture_shell_command'](console, recorder, name+'.log', name.replace('-', '_'), command, 20)
                if rc:
                    raise RuntimeError(name + ': rc=' + str(rc))
                return text
            target('console-quiet', 'echo N > /sys/module/printk/parameters/ignore_loglevel; dmesg -n 1')
            try:
                state = target('hid-state-reconnected', 'hid-keyboard state')
                if 'state=configured' not in state:
                    raise RuntimeError('UDC not configured')
                device = hid['wait_keyboard'](True, 10)
                hid['raw_keyboard'](device)
                hid['host_logs'](recorder, 'reconnected')
                with hid['InputCapture'](device, recorder) as capture:
                    try:
                        target('modifier-report', hid['modifier_command']())
                    finally:
                        target('release-report', 'hid-keyboard report')
                    result['hid']['input_report'] = capture.verify('report')
                with hid['InputCapture'](device, recorder) as capture:
                    try:
                        result['uvc'] = lab['run_uvc_test'](console, recorder, concurrent_hid=True, hid_report_command=hid['modifier_command']())
                    finally:
                        target('release-concurrent', 'hid-keyboard report')
                    result['hid']['concurrent_input_report'] = capture.verify('concurrent-report')
                if result['uvc']['result'] != 'passed':
                    raise RuntimeError('concurrent UVC failed')
                state = target('hid-final-state', 'dmesg; hid-keyboard state')
                monitor.stop()
                errors = hid['usb_errors'](state) + hid['usb_errors']((recorder.path/'host-kernel-live.log').read_text())
                errors += hid['usb_errors'](args.reconnect_evidence.with_name('host-kernel-live.log').read_text())
                result['hid']['usb_errors'] = {'passed': not errors, 'matching_lines': errors}
                if errors or 'state=configured' not in state:
                    raise RuntimeError('USB errors or UDC lost configuration')
                hid['host_logs'](recorder, 'after')
                result['result'] = 'passed'
            finally:
                target('console-restore', 'dmesg -n 8; echo Y > /sys/module/printk/parameters/ignore_loglevel')
    except Exception as error:
        result.update(result='failed', error=str(error))
    finally:
        monitor.stop()
        print(json.dumps(recorder.finish(result), indent=2), flush=True)


if __name__ == '__main__':
    main()
