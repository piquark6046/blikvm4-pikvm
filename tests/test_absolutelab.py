import copy
from pathlib import Path
import runpy
import struct
import unittest

ROOT = Path(__file__).resolve().parents[1]
G2 = runpy.run_path(str(ROOT / 'lab/absolutelab.py'))


class AbsoluteMouseTests(unittest.TestCase):
    def events(self):
        frames = [[(3, 0, 256), (3, 1, 512)], [(3, 0, 32511), (3, 1, 32255)],
                  [(3, 0, 16384), (3, 1, 8192)], [(1, 272, 1)], [(1, 272, 0)],
                  [(3, 0, 0), (3, 1, 0)]]
        return [dict(zip(('type', 'code', 'value'), event))
                for frame in frames for event in frame + [(0, 0, 0)]]

    def test_host_event_values_order_sync_and_cleanup(self):
        events = self.events()
        self.assertTrue(G2['assess_mouse'](events)['passed'])
        bad = []
        wrong = copy.deepcopy(events)
        wrong[0]['value'] = 257
        bad.append(wrong)
        bad.extend([events[:-3], events[3:] + events[:3], events[:-1],
                    events + [{'type': 0, 'code': 3, 'value': 0}],
                    [e for e in events if e['type'] != 0]])
        bad.append([dict(e, type=2) if e['type'] == 3 else e for e in events])
        for candidate in bad:
            with self.assertRaises(RuntimeError):
                G2['assess_mouse'](candidate)

    def test_capabilities_reject_relative_wheel_extra_buttons_and_signed_ranges(self):
        caps = {'keys': [272, 273, 274], 'absolute': [0, 1], 'relative': [],
                'axes': {str(i): {'min': 0, 'max': 32767, 'fuzz': 0, 'flat': 0} for i in (0, 1)}}
        G2['validate_caps'](caps)
        for field, value in [('keys', [272]), ('keys', [272, 273, 274, 275]),
                             ('absolute', [0, 1, 8]), ('relative', [0, 1])]:
            with self.assertRaises(RuntimeError):
                G2['validate_caps'](dict(caps, **{field: value}))
        for field, value in [('min', -32768), ('max', 65535), ('fuzz', 1)]:
            bad = copy.deepcopy(caps)
            bad['axes']['0'][field] = value
            with self.assertRaises(RuntimeError):
                G2['validate_caps'](bad)

    def test_descriptor_semantics_and_report_layout(self):
        # Parse HID short items independently to review actual global/local state.
        descriptor = G2['DESCRIPTOR']
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
                         (2, 1, 0, 32767, 16, 2, {0: [0x30, 0x31]}))
        self.assertEqual(sum(g[7] * g[9] for _, g, _ in inputs), 40)
        self.assertFalse(any(8 in g for _, g, _ in inputs))  # no report ID
        for buttons, x, y in G2['POINTS']:
            self.assertEqual(len(struct.pack('<BHH', buttons, x, y)), 5)
            self.assertTrue(0 <= x <= 32767 and 0 <= y <= 32767)

    def test_target_function_listing_accepts_columns_but_not_extra_functions(self):
        for separator in ('\n', '  ', '\t'):
            self.assertTrue(G2['valid_functions']('functions_begin\n' +
                separator.join(['hid.absolute', 'hid.keyboard']) + '\nfunctions_end'))
        for value in ('hid.keyboard', 'hid.absolute hid.keyboard hid.relative', ''):
            self.assertFalse(G2['valid_functions']('functions_begin\n' + value + '\nfunctions_end'))

    def test_exact_two_interface_binding(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            device = root / '1-3'
            device.mkdir()
            (device / 'speed').write_text('480')
            (device / 'descriptors').write_bytes(b'usb-descriptors')
            for index, (subclass, protocol) in enumerate([('01', '01'), ('00', '00')]):
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
            (root / '1-3:1.2').mkdir()
            self.assertFalse(G2['details'](device)['passed'])

    def test_g1_descriptor_still_exact(self):
        import re
        script = (ROOT / 'initramfs/hid-keyboard').read_text()
        octal = re.search(r"printf '((?:\\[0-7]{3})+)' > .*report_desc", script)[1]
        actual = bytes(int(s, 8) for s in octal.split('\\')[1:])
        self.assertEqual(actual, G2['G1']['REPORT_DESCRIPTOR'])
        self.assertEqual(len(actual), 63)
