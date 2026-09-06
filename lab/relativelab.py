"""G3 bridge qualification: frozen G1/G2 plus one relative pointer."""
from __future__ import annotations

import base64
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

G2 = runpy.run_path(str(Path(__file__).with_name('absolutelab.py')))
G1 = runpy.run_path(str(Path(__file__).with_name('hidlab.py')))
read = G1['read']
DESCRIPTOR = bytes.fromhex((Path(__file__).resolve().parents[1] /
                            'initramfs/hid-absolute-mouse.report.hex').read_text())
RELATIVE_DESCRIPTOR = bytes.fromhex((Path(__file__).resolve().parents[1] /
    'initramfs/hid-relative-mouse.report.hex').read_text())
DESCRIPTORS = [G1['REPORT_DESCRIPTOR'], DESCRIPTOR, RELATIVE_DESCRIPTOR]
RELATIVE_POINTS = [(0, 17, 0), (0, -23, 0), (0, 0, 31), (0, 0, -47),
                   (0, -11, 13), (1, 0, 0), (0, 0, 0), (0, 0, 0)]
POINTS = [(0, 256, 512), (0, 32511, 32255), (0, 16384, 8192),
          (1, 16384, 8192), (0, 16384, 8192), (0, 0, 0)]


def details(device):
    records = G1['keyboard_details'](device)
    interfaces = records['interfaces']
    expected = [('03', '01', '01', 'usbhid'), ('03', '00', '00', 'usbhid'), ('03', '00', '00', 'usbhid')]
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
    raise TimeoutError('G3 composite did not ' + ('enumerate' if present else 'disconnect'))


def interface_nodes(device, root, pattern, index):
    interface = (device.parent / (device.name + ':1.' + str(index))).resolve()
    return [p for p in root.glob(pattern) if interface in (p / 'device').resolve().parents]


def exact_descriptors(device, recorder, suffix):
    all_nodes = [p for p in Path('/sys/class/hidraw').glob('hidraw*')
                 if device.resolve() in (p / 'device').resolve().parents]
    if len(all_nodes) != 3:
        raise RuntimeError('expected exactly three hidraw nodes')
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
        assessment = (assess_relative(events) if self.index == 2 else
                      assess_mouse(events) if self.index == 1 else G1['assess_shift'](events))
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
        body = output.rsplit('functions_begin', 1)[1].split('functions_end', 1)[0]
    except IndexError:
        return False
    return sorted(body.split()) == ['hid.absolute', 'hid.keyboard', 'hid.relative']


IDENTITY_KEYS = ('keyboard_identity', 'mouse_identity', 'relative_identity')
FUNCTIONS = ('hid.keyboard', 'hid.absolute', 'hid.relative')


def relative_caps(fd):
    caps = {'keys': bits(ioctl_read(fd, 0x21, 96)),
            'absolute': bits(ioctl_read(fd, 0x23, 8)),
            'relative': bits(ioctl_read(fd, 0x22, 8)),
            'events': bits(ioctl_read(fd, 0x20, 8))}
    validate_relative_caps(caps)
    return caps


def validate_relative_caps(caps):
    if (caps['keys'] != [272, 273, 274] or caps['absolute'] or
            caps['relative'] != [0, 1] or 2 not in caps['events'] or 3 in caps['events']):
        raise RuntimeError('unexpected relative mouse capabilities: ' + str(caps))


def assess_relative(events):
    expected = [[(2, 0, 17)], [(2, 0, -23)], [(2, 1, 31)], [(2, 1, -47)],
                [(2, 0, -11), (2, 1, 13)], [(1, 272, 1)], [(1, 272, 0)]]
    frames, frame = [], []
    for e in events:
        triple = (e['type'], e['code'], e['value'])
        if triple == (0, 0, 0):
            frames.append(frame)
            frame = []
        elif e['type'] == 4 and e['code'] == 4:
            # Only the matching left-button usage scan is permitted.
            if e['value'] != 0x90001:
                raise RuntimeError('unexpected button usage scan')
        else:
            frame.append(triple)
    if frame or frames != expected:
        raise RuntimeError('host relative event order/values mismatch: ' + str(frames) + ' tail=' + str(frame))
    return {'passed': True, 'reports': RELATIVE_POINTS, 'frames': frames,
            'neutral_verified': True, 'neutral_generates_no_event': True}


def relative_command():
    writes = []
    for buttons, x, y in RELATIVE_POINTS:
        octal = ''.join('\\%03o' % b for b in struct.pack('<Bbb', buttons, x, y))
        writes.append("printf '" + octal + "' > \"$node\"; sleep 0.10")
    script = ('set -e; dev=$(cat /sys/kernel/config/usb_gadget/blikvm_m5/functions/hid.relative/dev); '
              'path=$(readlink -f "/sys/dev/char/$dev"); node=/dev/${path##*/}; [ -c "$node" ]; '
              "trap 'hid-relative-mouse report' EXIT; " + '; '.join(writes) + '; trap - EXIT')
    return 'timeout 5 sh -c ' + shlex.quote(script)


def concurrent_setup_commands():
    # BusyBox's interactive line editor truncates commands at 2047 bytes.
    # Stage byte-exact report scripts in RAM with bounded UART transactions.
    result = []
    for role, command in [('keyboard', G1['modifier_command']()),
                          ('absolute', mouse_command()), ('relative', relative_command())]:
        path = '/run/g3-' + role
        encoded = base64.b64encode((command + '\n').encode()).decode()
        result.append((role + '-init', ': > ' + path + '.b64'))
        for index in range(0, len(encoded), 400):
            result.append((role + '-' + str(index),
                           "printf '%s' '" + encoded[index:index+400] + "' >> " + path + '.b64'))
        result.append((role + '-decode', 'base64 -d ' + path + '.b64 > ' + path + '.sh'))
        digest = hashlib.sha256((command + '\n').encode()).hexdigest()
        result.append((role + '-verify', "printf '%s\\n' '" + digest + '  ' + path + ".sh' | sha256sum -c -"))
    return result


def concurrent_command():
    return ('( sh /run/g3-keyboard.sh & k=$!; sh /run/g3-absolute.sh & a=$!; '
            'sh /run/g3-relative.sh & r=$!; wait $k; ks=$?; wait $a; as=$?; '
            'wait $r; rs=$?; [ $ks -eq 0 ] && [ $as -eq 0 ] && [ $rs -eq 0 ] )')


def mapping_command(bound):
    # Resolve every function through its actual dev attribute; no hidg ordinal assumptions.
    script = r'''set -e; g=/sys/kernel/config/usb_gadget/blikvm_m5;
[ "$(ls "$g/functions" | sort)" = "$(printf 'hid.absolute\nhid.keyboard\nhid.relative')" ];
[ "$(ls "$g/configs/c.1" | grep '^hid\.' | sort)" = "$(printf 'hid.absolute\nhid.keyboard\nhid.relative')" ];
for f in hid.keyboard hid.absolute hid.relative; do
[ "$(readlink -f "$g/configs/c.1/$f")" = "$g/functions/$f" ];
dev=$(cat "$g/functions/$f/dev"); path=$(readlink -f "/sys/dev/char/$dev" || true);
node=/dev/${path##*/};
'''
    if bound:
        script += r'''[ -c "$node" ]; printf 'MAPPING %s %s %s\n' "$f" "$dev" "$node";
printf 'TARGET_DESCRIPTOR %s ' "$f"; od -An -v -tx1 "$g/functions/$f/report_desc" | tr -d ' \n'; echo;
'''
    else:
        script += r'''[ ! -c "$node" ];
'''
    script += 'done; '
    script += ('[ -n "$(cat "$g/UDC")" ]; [ "$(ls /dev/hidg* | wc -l)" -eq 3 ]' if bound else
               '[ -z "$(cat "$g/UDC")" ]; for n in /dev/hidg*; do [ ! -e "$n" ]; done')
    return '( ' + script.replace('\n', ' ') + ' )'


def parse_mapping(output, bound):
    if not bound:
        return {}
    result, descriptors = {}, {}
    for line in output.splitlines():
        fields = line.split()
        if fields and fields[0] == 'MAPPING' and len(fields) == 4:
            if fields[1] in result:
                raise RuntimeError('duplicate function mapping')
            result[fields[1]] = {'dev': fields[2], 'node': fields[3]}
        elif fields and fields[0] == 'TARGET_DESCRIPTOR' and len(fields) == 3:
            descriptors[fields[1]] = bytes.fromhex(fields[2])
    if set(result) != set(FUNCTIONS) or len({v['node'] for v in result.values()}) != 3 or len({v['dev'] for v in result.values()}) != 3:
        raise RuntimeError('missing/ambiguous function mapping')
    if descriptors != dict(zip(FUNCTIONS, DESCRIPTORS)):
        raise RuntimeError('target descriptor bytes differ')
    return result


def run_hid_test(console, recorder, args, run_uvc_test, capture):
    result = {'result': 'failed', 'slice': 'G3', 'failed_stage': 'setup', 'error': 'incomplete'}
    stage = 'setup'
    monitor = G1['HostMonitor'](recorder)

    def target(name, command):
        rc, output = capture(console, recorder, name + '.log', name.replace('-', '_'), command, 20)
        if rc:
            raise RuntimeError(name + ': target rc=' + str(rc))
        return output

    def state(suffix, bound):
        output = target('g3-state-' + suffix, 'hid-relative-mouse state')
        required = ('absolute_subclass=0', 'absolute_protocol=0', 'absolute_report_length=5',
                    'absolute_no_out_endpoint=1', 'relative_subclass=0', 'relative_protocol=0',
                    'relative_report_length=3', 'relative_no_out_endpoint=1')
        if any(s not in output.replace('\r', '') for s in required) or not valid_functions(output):
            raise RuntimeError('unexpected target function state')
        mapping = target('g3-mapping-' + suffix, mapping_command(bound))
        parsed = parse_mapping(mapping, bound)
        previous = result.setdefault('function_mapping', parsed if bound else None)
        if bound and previous != parsed:
            raise RuntimeError('function-to-hidg mapping changed')
        if bound and 'state=configured' not in output:
            raise RuntimeError('UDC not configured')
        return {'passed': True, 'bound': bound, 'mapping': parsed}

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
        with Capture(device, recorder, 2) as relative:
            record['relative_identity'] = relative.identity
            record['relative_capabilities'] = relative_caps(relative.fd)
        record['keyboard_identity'] = Capture(device, recorder, 0).identity
        identities = [record[k] for k in ('keyboard_identity', 'mouse_identity', 'relative_identity')]
        stable_inputs = [{k: v for k, v in i.items() if k not in ('node', 'sysfs')} for i in identities]
        if 'input_identity_baseline' in result and stable_inputs != result['input_identity_baseline']:
            raise RuntimeError('evdev identity/capabilities changed')
        result['input_identity_baseline'] = stable_inputs
        recorder.save_text('host-g3-' + suffix + '.json', json.dumps(record, indent=2))
        (recorder.path / ('host-usb-' + suffix + '.bin')).write_bytes((device / 'descriptors').read_bytes())
        G1['host_logs'](recorder, suffix)
        return device, record

    def functional(device, suffix, concurrent=False):
        with Capture(device, recorder, 0) as keyboard, Capture(device, recorder, 1) as mouse, Capture(device, recorder, 2) as relative:
            # All three devices are grabbed before *any* reports, including cleanup.
            target('g3-prime-' + suffix, 'hid-keyboard report; hid-absolute-mouse report; hid-relative-mouse report; sleep 0.2')
            keyboard.neutral()
            mouse.neutral()
            relative.neutral()
            try:
                if concurrent:
                    for name, command in concurrent_setup_commands():
                        target('g3-script-' + name, command)
                    result['uvc'] = run_uvc_test(console, recorder, concurrent_hid=True,
                        hid_report_command=concurrent_command())
                else:
                    target('g3-reports-' + suffix, G1['modifier_command']() + ' && ' + mouse_command() + ' && ' + relative_command())
            finally:
                target('g3-release-' + suffix, 'hid-keyboard report; hid-absolute-mouse report; hid-relative-mouse report; sleep 0.2')
            record = {'keyboard': keyboard.verify(suffix + '-keyboard'),
                      'absolute_mouse': mouse.verify(suffix + '-mouse'),
                      'relative_mouse': relative.verify(suffix + '-relative')}
            if concurrent and (result['uvc']['result'] != 'passed' or
                    int(result['uvc']['capture_summary']['startup_error_frames']) != 0):
                raise RuntimeError('concurrent UVC failed or contained startup errors')
            return record

    try:
        monitor.start()
        G1['host_logs'](recorder, 'before')
        target('g3-quiet', 'echo N > /sys/module/printk/parameters/ignore_loglevel; dmesg -n 1')
        target('udc-before', 'hid-keyboard state')
        target('g3-setup', 'hid-relative-mouse setup')
        target('g3-bind', 'hid-keyboard bind')
        stage = 'initial_enumeration_and_input'
        device, result['enumeration'] = snapshot('initial')
        state('initial', True)
        result['initial_input'] = functional(device, 'initial')
        stage = 'unbind_rebind'
        old_number = read(device / 'devnum')
        old_inputs = [result['enumeration'][k]['sysfs'] for k in IDENTITY_KEYS]
        target('g3-unbind', 'hid-keyboard unbind')
        wait_device(False, 10)
        if any(Path(p).exists() for p in old_inputs):
            raise RuntimeError('old HID input survived software unbind')
        state('unbound', False)
        target('g3-rebind', 'hid-keyboard bind')
        device, record = snapshot('rebound')
        if read(device / 'devnum') == old_number:
            raise RuntimeError('device number unchanged after rebind')
        state('rebound', True)
        result['unbind_rebind'] = {'passed': True, 'before': old_number, 'after': read(device / 'devnum'),
                                  'enumeration': record, 'input': functional(device, 'rebound')}
        stage = 'physical_reconnect'
        if args.reconnect_evidence:
            prior = json.loads(args.reconnect_evidence.read_text())
            if prior.get('hid', {}).get('slice') != 'G3':
                raise RuntimeError('physical evidence is not G3')
            result['physical_reconnect'] = G1['prior_reconnect'](args.reconnect_evidence, recorder.metadata['artifacts'])
        else:
            old_number = read(device / 'devnum')
            old_inputs = [record[k]['sysfs'] for k in IDENTITY_KEYS]
            print(f'G3_RECONNECT_READY run={recorder.run_id}; unplug USB-PC only, wait 2 seconds, reconnect',
                  file=sys.stderr, flush=True)
            wait_device(False, args.reconnect_timeout)
            disconnected_at = time.time()
            recorder.save_text('host-disconnected.json', json.dumps({
                'time': disconnected_at, 'device_absent': G1['keyboard_device']() is None,
                'old_inputs_absent': [not Path(p).exists() for p in old_inputs]}))
            if any(Path(p).exists() for p in old_inputs):
                raise RuntimeError('old HID sysfs survived disconnect')
            device = wait_device(True, args.reconnect_timeout)
            number = read(device / 'devnum')
            time.sleep(3)
            if read(device / 'devnum') != number or not details(device)['passed']:
                raise RuntimeError('unstable physical re-enumeration')
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
        target('g3-quiet-after-uvc', 'echo N > /sys/module/printk/parameters/ignore_loglevel; dmesg -n 1')
        result['final_state'] = state('final', True)
        _, result['final_enumeration'] = snapshot('final')
        stage = 'usb_errors'
        dmesg = target('g3-dmesg-after', 'dmesg')
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
            target('g3-final-collection', 'dmesg; hid-relative-mouse state')
            G1['host_logs'](recorder, 'after')
            target('g3-console-restore', 'dmesg -n 8; echo Y > /sys/module/printk/parameters/ignore_loglevel')
        except Exception as error:
            result['collection_error'] = str(error)
            if result['result'] == 'passed':
                result.update(result='failed', failed_stage='collect', error=str(error))
    return result
