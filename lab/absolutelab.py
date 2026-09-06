"""G2 bridge qualification: unchanged G1 keyboard plus one absolute pointer."""
from __future__ import annotations

import fcntl
import hashlib
import json
import os
from pathlib import Path
import runpy
import select
import shlex
import struct
import sys
import time

G1 = runpy.run_path(str(Path(__file__).with_name('hidlab.py')))
read = G1['read']
DESCRIPTOR = bytes.fromhex((Path(__file__).resolve().parents[1] /
                            'initramfs/hid-absolute-mouse.report.hex').read_text())
DESCRIPTORS = [G1['REPORT_DESCRIPTOR'], DESCRIPTOR]
POINTS = [(0, 256, 512), (0, 32511, 32255), (0, 16384, 8192),
          (1, 16384, 8192), (0, 16384, 8192), (0, 0, 0)]


def details(device):
    records = G1['keyboard_details'](device)
    interfaces = records['interfaces']
    expected = [('03', '01', '01', 'usbhid'), ('03', '00', '00', 'usbhid')]
    actual = [(p['class'], p['subclass'], p['protocol'], p['driver']) for p in interfaces]
    records['passed'] = records['speed'] == '480' and actual == expected
    records['identity'] = {a: read(device / a) for a in
                           ('idVendor', 'idProduct', 'bcdDevice', 'manufacturer', 'product', 'serial')}
    records['usb_descriptors_sha256'] = hashlib.sha256((device / 'descriptors').read_bytes()).hexdigest()
    return records


def wait_device(present, timeout):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        device = G1['keyboard_device']()
        if not present and device is None:
            return None
        if present and device is not None and details(device)['passed']:
            return device
        time.sleep(0.1)
    raise TimeoutError('G2 composite did not ' + ('enumerate' if present else 'disconnect'))


def interface_nodes(device, root, pattern, index):
    interface = (device.parent / (device.name + ':1.' + str(index))).resolve()
    return [p for p in root.glob(pattern) if interface in (p / 'device').resolve().parents]


def exact_descriptors(device, recorder, suffix):
    all_nodes = [p for p in Path('/sys/class/hidraw').glob('hidraw*')
                 if device.resolve() in (p / 'device').resolve().parents]
    if len(all_nodes) != 2:
        raise RuntimeError('expected exactly two hidraw nodes')
    result = []
    for index, expected in enumerate(DESCRIPTORS):
        nodes = interface_nodes(device, Path('/sys/class/hidraw'), 'hidraw*', index)
        if len(nodes) != 1:
            raise RuntimeError('missing or ambiguous hidraw interface ' + str(index))
        actual = (nodes[0] / 'device/report_descriptor').read_bytes()
        recorder.save_text(f'host-report-{suffix}-{index}.hex', actual.hex() + '\n')
        (recorder.path / f'host-report-{suffix}-{index}.bin').write_bytes(actual)
        if actual != expected:
            raise RuntimeError('report descriptor mismatch on interface ' + str(index))
        result.append({'interface': index, 'hex': actual.hex(), 'sha256': hashlib.sha256(actual).hexdigest()})
    return result


def ioctl_read(fd, number, length):
    buf = bytearray(length)
    fcntl.ioctl(fd, 0x80000000 | (length << 16) | (ord('E') << 8) | number, buf)
    return bytes(buf)


def bits(data):
    return [i for i in range(len(data) * 8) if data[i // 8] & (1 << (i % 8))]


def mouse_caps(fd):
    caps = {'keys': bits(ioctl_read(fd, 0x21, 96)),
            'absolute': bits(ioctl_read(fd, 0x23, 8)),
            'relative': bits(ioctl_read(fd, 0x22, 8)), 'axes': {}}
    for axis in (0, 1):
        caps['axes'][str(axis)] = dict(zip(('value', 'min', 'max', 'fuzz', 'flat', 'resolution'),
                                         struct.unpack('6i', ioctl_read(fd, 0x40 + axis, 24))))
    validate_caps(caps)
    return caps


def validate_caps(caps):
    if caps['keys'] != [272, 273, 274] or caps['absolute'] != [0, 1] or caps['relative']:
        raise RuntimeError('unexpected mouse button/axis capabilities: ' + str(caps))
    if any((a['min'], a['max'], a['fuzz'], a['flat']) != (0, 32767, 0, 0)
           for a in caps['axes'].values()):
        raise RuntimeError('unexpected absolute axis range/filtering')


def assess_mouse(events):
    # Reports start at a verified neutral state. evdev suppresses unchanged values.
    expected = [[(3, 0, 256), (3, 1, 512)],
                [(3, 0, 32511), (3, 1, 32255)],
                [(3, 0, 16384), (3, 1, 8192)],
                [(1, 272, 1)], [(1, 272, 0)], [(3, 0, 0), (3, 1, 0)]]
    frames, frame = [], []
    for e in events:
        triple = (e['type'], e['code'], e['value'])
        if triple == (0, 0, 0):
            frames.append(frame)
            frame = []
        elif e['type'] == 4 and e['code'] == 4:  # optional MSC_SCAN on buttons
            continue
        else:
            frame.append(triple)
    if frame or frames != expected:
        raise RuntimeError('host absolute event order/values mismatch: ' + str(frames) + ' tail=' + str(frame))
    return {'passed': True, 'reports': POINTS, 'frames': frames, 'neutral_verified': True}


class Capture(G1['InputCapture']):
    def __init__(self, device, recorder, index):
        nodes = interface_nodes(device, Path('/sys/class/input'), 'event*', index)
        if len(nodes) != 1:
            raise RuntimeError('expected one evdev device for interface ' + str(index))
        p = nodes[0]
        self.identity = {'node': '/dev/input/' + p.name, 'sysfs': str((p / 'device').resolve()),
                         'interface': index, **{a: read(p / 'device' / a) for a in
                          ('name', 'phys', 'uniq', 'id/vendor', 'id/product', 'capabilities/key')}}
        if self.identity['id/vendor'] != '1d6b' or self.identity['id/product'] != '0106':
            raise RuntimeError('evdev identity mismatch')
        self.recorder, self.fd, self.index = recorder, None, index

    def collect(self):
        data = b''
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            if select.select([self.fd], [], [], 0.2)[0]:
                data += os.read(self.fd, G1['INPUT_EVENT'].size * 64)
            elif data:
                break
        return G1['decode_input'](data)

    def neutral(self):
        keys = bits(ioctl_read(self.fd, 0x18, 96))
        if keys:
            raise RuntimeError('keys/buttons still pressed: ' + str(keys))
        if self.index == 1:
            caps = mouse_caps(self.fd)
            if any(a['value'] != 0 for a in caps['axes'].values()):
                raise RuntimeError('mouse did not return to neutral coordinates')
        # Drain any neutralization events before the deterministic sequence.
        while select.select([self.fd], [], [], 0)[0]:
            os.read(self.fd, 4096)

    def verify(self, suffix):
        events = self.collect()
        record = {'identity': self.identity, 'events': events}
        self.recorder.save_text('host-input-' + suffix + '.json', json.dumps(record, indent=2))
        assessment = assess_mouse(events) if self.index == 1 else G1['assess_shift'](events)
        self.neutral()
        return {**assessment, **record}


def mouse_command():
    writes = []
    for buttons, x, y in POINTS:
        report = struct.pack('<BHH', buttons, x, y)
        octal = ''.join('\\%03o' % b for b in report)
        writes.append("printf '" + octal + "' > \"$node\"; sleep 0.15")
    script = ('set -e; dev=$(cat /sys/kernel/config/usb_gadget/blikvm_m5/functions/hid.absolute/dev); '
              'path=$(readlink -f "/sys/dev/char/$dev"); node=/dev/${path##*/}; [ -c "$node" ]; '
              "trap 'hid-absolute-mouse report' EXIT; " + '; '.join(writes) + '; trap - EXIT')
    return 'timeout 5 sh -c ' + shlex.quote(script)


def valid_functions(output):
    try:
        body = output.split('functions_begin', 1)[1].split('functions_end', 1)[0]
    except IndexError:
        return False
    return sorted(body.split()) == ['hid.absolute', 'hid.keyboard']


def run_hid_test(console, recorder, args, run_uvc_test, capture):
    result = {'result': 'failed', 'slice': 'G2', 'failed_stage': 'setup', 'error': 'incomplete'}
    stage = 'setup'
    monitor = G1['HostMonitor'](recorder)

    def target(name, command):
        rc, output = capture(console, recorder, name + '.log', name.replace('-', '_'), command, 20)
        if rc:
            raise RuntimeError(name + ': target rc=' + str(rc))
        return output

    def state(suffix, bound):
        output = target('g2-state-' + suffix, 'hid-absolute-mouse state')
        required = ('absolute_subclass=0', 'absolute_protocol=0', 'absolute_report_length=5',
                    'absolute_no_out_endpoint=1')
        if any(s not in output.replace('\r', '') for s in required) or not valid_functions(output):
            raise RuntimeError('unexpected target function state')
        command = ('g=/sys/kernel/config/usb_gadget/blikvm_m5; '
                   '[ "$(ls "$g/configs/c.1" | grep "^hid\\.")" = "$(printf "hid.absolute\\nhid.keyboard")" ]; '
                   '[ "$(readlink -f "$g/configs/c.1/hid.keyboard")" = "$g/functions/hid.keyboard" ] && '
                   '[ "$(readlink -f "$g/configs/c.1/hid.absolute")" = "$g/functions/hid.absolute" ] && ')
        command += ('[ -n "$(cat "$g/UDC")" ] && [ "$(ls /dev/hidg* | wc -l)" -eq 2 ]' if bound else
                    '[ -z "$(cat "$g/UDC")" ] && [ ! -e /dev/hidg0 ] && [ ! -e /dev/hidg1 ]')
        target('g2-clean-' + suffix, '( set -e; ' + command + ' )')
        if bound and 'state=configured' not in output:
            raise RuntimeError('UDC not configured')
        return {'passed': True, 'bound': bound}

    baseline = None
    def snapshot(suffix):
        nonlocal baseline
        device = wait_device(True, 15)
        record = details(device)
        stable = (record['identity'], record['usb_descriptors_sha256'])
        if baseline is not None and stable != baseline:
            raise RuntimeError('USB identity or descriptors changed')
        baseline = stable
        record['reports'] = exact_descriptors(device, recorder, suffix)
        with Capture(device, recorder, 1) as mouse:
            record['mouse_identity'] = mouse.identity
            record['capabilities'] = mouse_caps(mouse.fd)
        record['keyboard_identity'] = Capture(device, recorder, 0).identity
        recorder.save_text('host-g2-' + suffix + '.json', json.dumps(record, indent=2))
        (recorder.path / ('host-usb-' + suffix + '.bin')).write_bytes((device / 'descriptors').read_bytes())
        G1['host_logs'](recorder, suffix)
        return device, record

    def functional(device, suffix, concurrent=False):
        with Capture(device, recorder, 0) as keyboard, Capture(device, recorder, 1) as mouse:
            # Both devices are grabbed before *any* reports, including cleanup.
            target('g2-prime-' + suffix, 'hid-keyboard report; hid-absolute-mouse report; sleep 0.2')
            keyboard.neutral()
            mouse.neutral()
            try:
                if concurrent:
                    result['uvc'] = run_uvc_test(console, recorder, concurrent_hid=True,
                        hid_report_command=G1['modifier_command']() + ' && ' + mouse_command())
                else:
                    target('g2-reports-' + suffix, G1['modifier_command']() + ' && ' + mouse_command())
            finally:
                target('g2-release-' + suffix, 'hid-keyboard report; hid-absolute-mouse report; sleep 0.2')
            record = {'keyboard': keyboard.verify(suffix + '-keyboard'),
                      'absolute_mouse': mouse.verify(suffix + '-mouse')}
            if concurrent and (result['uvc']['result'] != 'passed' or
                    int(result['uvc']['capture_summary']['startup_error_frames']) != 0):
                raise RuntimeError('concurrent UVC failed or contained startup errors')
            return record

    try:
        monitor.start()
        G1['host_logs'](recorder, 'before')
        target('g2-quiet', 'echo N > /sys/module/printk/parameters/ignore_loglevel; dmesg -n 1')
        target('udc-before', 'hid-keyboard state')
        target('g2-setup', 'hid-absolute-mouse setup')
        target('g2-bind', 'hid-keyboard bind')
        stage = 'initial_enumeration_and_input'
        device, result['enumeration'] = snapshot('initial')
        state('initial', True)
        result['initial_input'] = functional(device, 'initial')
        stage = 'unbind_rebind'
        old_number = read(device / 'devnum')
        target('g2-unbind', 'hid-keyboard unbind')
        wait_device(False, 10)
        state('unbound', False)
        target('g2-rebind', 'hid-keyboard bind')
        device, record = snapshot('rebound')
        if read(device / 'devnum') == old_number:
            raise RuntimeError('device number unchanged after rebind')
        state('rebound', True)
        result['unbind_rebind'] = {'passed': True, 'before': old_number, 'after': read(device / 'devnum'),
                                  'enumeration': record, 'input': functional(device, 'rebound')}
        stage = 'physical_reconnect'
        if args.reconnect_evidence:
            prior = json.loads(args.reconnect_evidence.read_text())
            if prior.get('hid', {}).get('slice') != 'G2':
                raise RuntimeError('physical evidence is not G2')
            result['physical_reconnect'] = G1['prior_reconnect'](args.reconnect_evidence, recorder.metadata['artifacts'])
        else:
            old_number = read(device / 'devnum')
            old_input = record['mouse_identity']['sysfs']
            print(f'G2_RECONNECT_READY run={recorder.run_id}; unplug USB-PC only, wait 2 seconds, reconnect',
                  file=sys.stderr, flush=True)
            wait_device(False, args.reconnect_timeout)
            disconnected_at = time.time()
            recorder.save_text('host-disconnected.json', json.dumps({
                'time': disconnected_at, 'device_absent': G1['keyboard_device']() is None,
                'old_mouse_sysfs_absent': not Path(old_input).exists()}))
            if Path(old_input).exists():
                raise RuntimeError('old mouse sysfs survived disconnect')
            device = wait_device(True, args.reconnect_timeout)
            if read(device / 'devnum') == old_number:
                raise RuntimeError('device number unchanged after physical reconnect')
            result['physical_reconnect'] = {'passed': True, 'repeated_this_boot': True,
                'disconnected_at': disconnected_at, 'reconnected_at': time.time(),
                'before': old_number, 'after': read(device / 'devnum'), 'old_input_removed': True}
        device, result['reconnected_enumeration'] = snapshot('reconnected')
        state('reconnected', True)
        stage = 'reconnected_input'
        result['reconnected_input'] = functional(device, 'reconnected')
        stage = 'concurrent_uvc'
        result['concurrent_input'] = functional(device, 'concurrent', concurrent=True)
        # UVC restores console verbosity; suppress it again for marker transactions.
        target('g2-quiet-after-uvc', 'echo N > /sys/module/printk/parameters/ignore_loglevel; dmesg -n 1')
        result['final_state'] = state('final', True)
        _, result['final_enumeration'] = snapshot('final')
        stage = 'usb_errors'
        dmesg = target('g2-dmesg-after', 'dmesg')
        monitor.stop()
        errors = G1['usb_errors'](dmesg) + G1['usb_errors'](read(recorder.path / 'host-kernel-live.log'))
        result['usb_errors'] = {'passed': not errors, 'matching_lines': errors}
        if errors:
            raise RuntimeError('USB errors: ' + str(errors))
        result.update(result='passed', failed_stage=None, error=None)
    except Exception as error:
        result.update(result='failed', failed_stage=stage, error=str(error))
    finally:
        monitor.stop()
        try:
            target('g2-final-collection', 'dmesg; hid-absolute-mouse state')
            G1['host_logs'](recorder, 'after')
            target('g2-console-restore', 'dmesg -n 8; echo Y > /sys/module/printk/parameters/ignore_loglevel')
        except Exception as error:
            result['collection_error'] = str(error)
            if result['result'] == 'passed':
                result.update(result='failed', failed_stage='collect', error=str(error))
    return result
