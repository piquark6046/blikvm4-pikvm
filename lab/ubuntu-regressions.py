#!/usr/bin/env python3
"""M7-D on a qualified live Ubuntu RAM root, reusing frozen M5 test primitives."""
from concurrent.futures import ThreadPoolExecutor
import argparse
import hashlib
import json
from pathlib import Path
import re
import runpy
import threading

ROOT = Path(__file__).resolve().parents[1]
LAB = runpy.run_path(str(ROOT / 'lab/labctl'))
G4 = runpy.run_path(str(ROOT / 'lab/storagelab.py'))
G1 = G4['G1']


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--boot-result', type=Path, required=True)
    p.add_argument('--out-root', type=Path, required=True)
    a = p.parse_args()
    prior = json.loads(a.boot_result.read_text())
    if prior.get('result') != 'passed' or prior.get('stage') != 'ubuntu_network_ssh':
        raise RuntimeError('M7-B/C must pass before hardware regression testing')
    r = LAB['RunRecorder']('ubuntu-hardware-regressions', a.out_root)
    metadata = json.loads((Path(prior['run_directory']) / 'metadata.json').read_text())
    r.metadata.update(artifacts=metadata['artifacts'], build_source=metadata['build_source'],
                      ubuntu_boot_run=prior['run_id'])
    r.save_text('runner.py', Path(__file__).read_text())
    result = {'result': 'failed', 'boot_run': prior['run_id'], 'stage': 'preflight'}
    monitor = G1['HostMonitor'](r)
    try:
        with LAB['SerialConsole'](Path('/dev/serial/by-id/usb-1a86_USB_Serial-if00-port0'), r) as c:
            def target(name, command, timeout=30):
                rc, text = LAB['capture_shell_command'](c, r, name + '.log', name.replace('-', '_'),
                                                       '(set -e; ' + command + ')', timeout)
                if rc:
                    raise RuntimeError(f'{name}: target rc={rc}')
                return text
            c.write_line(b'')
            c.read_for(.2)
            prior_identity = (Path(prior['run_directory']) / 'identity.log').read_text()
            live_boot_id = target('boot-id', 'cat /proc/sys/kernel/random/boot_id').strip()
            if not re.fullmatch(r'[0-9a-f-]{36}', live_boot_id) or live_boot_id not in prior_identity.splitlines():
                raise RuntimeError('live boot does not match the M7-B/C evidence')
            result['boot_id'] = live_boot_id
            target('identity', 'test "$(cat /proc/1/comm)" = systemd; uname -a; cat /etc/os-release /etc/blikvm-build')
            result['stage'] = 'mmc'
            target('mmc-readonly', 'for d in /dev/mmcblk0 /dev/mmcblk0p*; do blockdev --setro "$d"; test "$(blockdev --getro "$d")" = 1; done; test "$(cat /sys/block/mmcblk0/size)" = 125173760; test "$(cat /sys/bus/mmc/devices/mmc0:*/name)" = EC1S5; lsblk -J -b -o NAME,SIZE,RO,FSTYPE,TYPE,MOUNTPOINTS; blkid; mkdir -p /mnt/mmc-test; mount -t ext4 -o ro,noload /dev/mmcblk0p1 /mnt/mmc-test; trap "umount /mnt/mmc-test" EXIT; cat /mnt/mmc-test/etc/os-release; sha256sum /mnt/mmc-test/etc/os-release')
            result['mmc'] = {'passed': True, 'mount': 'ro,noload', 'writes': False}
            result['stage'] = 'emac_ehci_uvc_udc'
            target('hardware-inventory', 'ip -br addr; ip route; ethtool eth0; ping -c 5 -W 2 192.168.88.1; test "$(cat /sys/class/net/eth0/carrier)" = 1; test "$(basename "$(readlink /sys/bus/platform/devices/5200000.usb/driver)")" = ehci-platform; test "$(cat /sys/bus/usb/devices/1-1/idVendor):$(cat /sys/bus/usb/devices/1-1/idProduct)" = 345f:2131; test "$(cat /sys/bus/usb/devices/1-1/serial)" = 29404080; lsusb; lsusb -t; v4l2-ctl --list-devices; v4l2-ctl --list-formats-ext; ls -l /sys/class/udc; hid-keyboard state', 45)
            monitor.start()
            target('console-quiet', 'echo N > /sys/module/printk/parameters/ignore_loglevel; dmesg -n 1')
            target('gadget-setup', 'gadget-storage setup; hid-keyboard bind')

            def enumerate_device(label):
                d = G4['wait_device'](True, 20)
                details = G4['details'](d)
                if not details['passed']:
                    raise RuntimeError('host interface binding failed')
                r.save_text('host-' + label + '.json', json.dumps(details, indent=2))
                G4['exact_descriptors'](d, r, label)
                G1['host_logs'](r, label)
                output = target('gadget-state-' + label, 'gadget-storage state')
                if not G4['valid_functions'](output) or 'state=configured' not in output:
                    raise RuntimeError('target gadget state mismatch')
                target('function-map-' + label, G4['mapping_command'](True))
                return d

            def inputs(d, label, concurrent=False):
                with G4['Capture'](d, r, 0) as keyboard, G4['Capture'](d, r, 1) as absolute, G4['Capture'](d, r, 2) as relative:
                    G4['mouse_caps'](absolute.fd)
                    G4['relative_caps'](relative.fd)
                    target('neutral-' + label, 'hid-keyboard report; hid-absolute-mouse report; hid-relative-mouse report; sleep .2')
                    for capture in (keyboard, absolute, relative):
                        capture.neutral()
                    try:
                        if concurrent:
                            for name, command in G4['concurrent_setup_commands']():
                                target('script-' + name, command)
                            stopped = threading.Event()
                            with ThreadPoolExecutor(max_workers=1) as pool:
                                future = pool.submit(G4['storage_during_uvc'], d, r, stopped)
                                try:
                                    result['uvc'] = LAB['run_uvc_test'](c, r, concurrent_hid=True,
                                                                  hid_report_command=G4['concurrent_command']())
                                finally:
                                    stopped.set()
                                result['concurrent_storage'] = future.result()
                            if result['uvc']['result'] != 'passed' or int(result['uvc']['capture_summary']['startup_error_frames']) != 0:
                                raise RuntimeError('bounded UVC capture failed or had startup errors')
                        else:
                            target('reports-' + label, G1['modifier_command']() + ' && ' + G4['mouse_command']() + ' && ' + G4['relative_command']())
                    finally:
                        target('release-' + label, 'hid-keyboard report; hid-absolute-mouse report; hid-relative-mouse report; sleep .2')
                    return {'keyboard': keyboard.verify(label + '-keyboard'),
                            'absolute': absolute.verify(label + '-absolute'),
                            'relative': relative.verify(label + '-relative')}

            result['stage'] = 'hid_storage'
            d = enumerate_device('initial')
            result['storage'] = G4['storage_test'](d, r, 'ubuntu')
            result['inputs'] = inputs(d, 'initial')
            result['stage'] = 'rebind'
            old = G4['read'](d / 'devnum')
            target('unbind', 'hid-keyboard unbind')
            G4['wait_device'](False, 10)
            target('rebind', 'hid-keyboard bind')
            d = enumerate_device('rebound')
            if G4['read'](d / 'devnum') == old:
                raise RuntimeError('host device did not re-enumerate')
            result['rebound_inputs'] = inputs(d, 'rebound')
            result['stage'] = 'concurrent_uvc_hid_storage'
            result['concurrent_inputs'] = inputs(d, 'concurrent', concurrent=True)
            target('quiet-after', 'echo N > /sys/module/printk/parameters/ignore_loglevel; dmesg -n 1')
            dmesg = target('dmesg', 'dmesg')
            target('systemctl-failed', 'systemctl --failed --no-pager; test "$(systemctl --failed --no-legend --plain | wc -l)" -eq 0')
            monitor.stop()
            host_log = (r.path / 'host-kernel-live.log').read_text()
            errors = G1['usb_errors'](dmesg) + G1['usb_errors'](host_log) + G4['unexpected_resets'](host_log)
            if errors:
                raise RuntimeError('unexpected USB errors: ' + str(errors))
            result.update(result='passed', stage='ubuntu_hardware_regressions', usb_errors=[])
    except Exception as error:
        result['error'] = str(error)
    finally:
        monitor.stop()
    print(json.dumps(r.finish(result)), flush=True)
    return result['result'] == 'passed'


if __name__ == '__main__':
    raise SystemExit(0 if main() else 1)
