import copy
from pathlib import Path
import runpy
import struct
import unittest

ROOT = Path(__file__).resolve().parents[1]
G2 = runpy.run_path(str(ROOT / 'lab/relativelab.py'))


class RelativeMouseTests(unittest.TestCase):
    def events(self):
        frames = [[(2, 0, 17)], [(2, 0, -23)], [(2, 1, 31)], [(2, 1, -47)],
                  [(2, 0, -11), (2, 1, 13)], [(1, 272, 1)], [(1, 272, 0)]]
        return [dict(zip(('type', 'code', 'value'), event))
                for frame in frames for event in frame + [(0, 0, 0)]]

    def test_host_event_values_order_sync_and_cleanup(self):
        events = self.events()
        self.assertTrue(G2['assess_relative'](events)['passed'])
        bad = []
        wrong = copy.deepcopy(events)
        wrong[0]['value'] = 257
        bad.append(wrong)
        bad.extend([events[:-3], events[3:] + events[:3], events[:-1],
                    events + [{'type': 0, 'code': 3, 'value': 0}],
                    [e for e in events if e['type'] != 0]])
        bad.append([dict(e, type=3) if e['type'] == 2 else e for e in events])
        for candidate in bad:
            with self.assertRaises(RuntimeError):
                G2['assess_relative'](candidate)

    def test_exact_relative_capabilities(self):
        caps = {'keys': [272, 273, 274], 'absolute': [], 'relative': [0, 1], 'events': [0, 1, 2, 4]}
        G2['validate_relative_caps'](caps)
        for field, value in [('keys', [272]), ('keys', [272, 273, 274, 275]),
                             ('absolute', [0, 1]), ('relative', [0, 1, 8]),
                             ('relative', [0]), ('events', [0, 1, 3])]:
            with self.assertRaises(RuntimeError):
                G2['validate_relative_caps'](dict(caps, **{field: value}))

    def test_descriptor_semantics_and_report_layout(self):
        # Parse HID short items independently to review actual global/local state.
        descriptor = G2['RELATIVE_DESCRIPTOR']
        pos, globals_, locals_, inputs, depth = 0, {}, {}, [], 0
        while pos < len(descriptor):
            prefix = descriptor[pos]
            pos += 1
            size = [0, 1, 2, 4][prefix & 3]
            payload = descriptor[pos:pos+size]
            self.assertEqual(len(payload), size)
            pos += size
            kind, tag = (prefix >> 2) & 3, prefix >> 4
            value = int.from_bytes(payload, 'little')
            if kind == 1:
                globals_[tag] = value
            elif kind == 2:
                locals_.setdefault(tag, []).append(value)
            elif kind == 0:
                if tag == 8:
                    inputs.append((value, globals_.copy(), locals_.copy()))
                elif tag == 10:
                    depth += 1
                elif tag == 12:
                    depth -= 1
                else:
                    self.fail('unexpected main item (output/feature)')
                locals_ = {}
        self.assertEqual(depth, 0)
        self.assertEqual(len(inputs), 3)
        buttons, padding, axes = inputs
        self.assertEqual((buttons[0], buttons[1][0], buttons[1][1], buttons[1][2],
                          buttons[1][7], buttons[1][9], buttons[2]),
                         (2, 9, 0, 1, 1, 3, {1: [1], 2: [3]}))
        self.assertEqual((padding[0], padding[1][7], padding[1][9]), (1, 5, 1))
        self.assertEqual((axes[0], axes[1][0], axes[1][1], axes[1][2],
                          axes[1][7], axes[1][9], axes[2]),
                         (6, 1, 129, 127, 8, 2, {0: [0x30, 0x31]}))
        self.assertEqual(sum(g[7] * g[9] for _, g, _ in inputs), 24)
        self.assertFalse(any(8 in g for _, g, _ in inputs))  # no report ID
        for buttons, x, y in G2['RELATIVE_POINTS']:
            self.assertEqual(len(struct.pack('<Bbb', buttons, x, y)), 3)
            self.assertTrue(-127 <= x <= 127 and -127 <= y <= 127)

    def test_target_function_listing_accepts_columns_but_not_extra_functions(self):
        for separator in ('\n', '  ', '\t'):
            self.assertTrue(G2['valid_functions']('functions_begin\n' +
                separator.join(['hid.absolute', 'hid.keyboard', 'hid.relative']) + '\nfunctions_end'))
        for value in ('hid.keyboard', 'hid.absolute hid.keyboard', ''):
            self.assertFalse(G2['valid_functions']('functions_begin\n' + value + '\nfunctions_end'))

    def test_exact_three_interface_binding(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            device = root / '1-3'
            device.mkdir()
            (device / 'speed').write_text('480')
            (device / 'descriptors').write_bytes(b'usb-descriptors')
            for index, (subclass, protocol) in enumerate([('01', '01'), ('00', '00'), ('00', '00')]):
                interface = root / ('1-3:1.' + str(index))
                interface.mkdir()
                for name, value in [('bInterfaceClass', '03'), ('bInterfaceSubClass', subclass),
                                    ('bInterfaceProtocol', protocol)]:
                    (interface / name).write_text(value)
                (interface / 'driver').symlink_to('/drivers/usbhid')
            self.assertTrue(G2['details'](device)['passed'])
            (root / '1-3:1.1/driver').unlink()
            self.assertFalse(G2['details'](device)['passed'])
            (root / '1-3:1.1/driver').symlink_to('/drivers/usbhid')
            (root / '1-3:1.3').mkdir()
            self.assertFalse(G2['details'](device)['passed'])

    def test_g1_descriptor_still_exact(self):
        import re
        script = (ROOT / 'initramfs/hid-keyboard').read_text()
        octal = re.search(r"printf '((?:\\[0-7]{3})+)' > .*report_desc", script)[1]
        actual = bytes(int(s, 8) for s in octal.split('\\')[1:])
        self.assertEqual(actual, G2['G1']['REPORT_DESCRIPTOR'])
        self.assertEqual(len(actual), 63)

    def test_frozen_g2_descriptor(self):
        import hashlib
        self.assertEqual(hashlib.sha256(G2['DESCRIPTOR']).hexdigest(),
                         'b17306893223490b3e65f4b99477cad3380bcfcb0d3fa2ee0971fbf41e90111a')

    def test_mapping_uses_function_identity_and_exact_target_descriptors(self):
        text = ''
        for i, (name, desc) in enumerate(zip(G2['FUNCTIONS'], G2['DESCRIPTORS'])):
            text += f'MAPPING {name} 240:{i+4} /dev/hidg{i+4}\nTARGET_DESCRIPTOR {name} {desc.hex()}\n'
        self.assertEqual(G2['parse_mapping'](text, True)['hid.keyboard']['node'], '/dev/hidg4')
        for bad in (text.replace('/dev/hidg5', '/dev/hidg4'),
                    text.replace('240:5', '240:4'), text.replace('hid.relative', 'hid.extra'),
                    text.replace(G2['RELATIVE_DESCRIPTOR'].hex(), '00')):
            with self.assertRaises(RuntimeError):
                G2['parse_mapping'](bad, True)

    def test_concurrent_uart_commands_are_bounded_and_preserve_report_scripts(self):
        import base64
        import hashlib
        commands = G2['concurrent_setup_commands']()
        for name, command in commands:
            self.assertLess(len(command), 700)
        self.assertLess(len(G2['concurrent_command']()), 300)
        for role, original in [('keyboard', G2['G1']['modifier_command']()),
                               ('absolute', G2['mouse_command']()),
                               ('relative', G2['relative_command']())]:
            chunks = [command.split("'")[3] for name, command in commands
                      if name.startswith(role + '-') and name.split('-')[-1].isdigit()]
            decoded = base64.b64decode(''.join(chunks))
            self.assertEqual(decoded, (original + '\n').encode())
            self.assertIn(hashlib.sha256(decoded).hexdigest(),
                          dict(commands)[role + '-verify'])
