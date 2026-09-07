"""M8-D identity failures must fail closed before granting HID access."""
import os
from pathlib import Path
import runpy
import stat
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
RESOLVE = runpy.run_path(str(ROOT / 'build/kvmd-hid/resolve-hid.py'))['resolve']


class HidIdentityTests(unittest.TestCase):
    def fixture(self, root):
        sysroot, devroot, desc = [root / name for name in ('sys', 'dev', 'descriptors')]
        gadget = sysroot / 'kernel/config/usb_gadget/blikvm_m5'
        def put(p, value):
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(value)
        controller = sysroot / 'devices/platform/5100000.usb/musb/udc/test'
        controller.mkdir(parents=True)
        udcs = sysroot / 'class/udc'; udcs.mkdir(parents=True)
        (udcs / 'test').symlink_to(controller)
        put(gadget / 'UDC', 'test')
        (gadget / 'functions/mass_storage.g4').mkdir(parents=True)
        (gadget / 'configs/c.1').mkdir(parents=True)
        numbers = {}
        # Deliberately nonsequential and reordered, with an unrelated fourth node.
        for role, minor, length in [('keyboard', 9, 8), ('absolute', 2, 5), ('relative', 6, 3)]:
            fn = gadget / 'functions' / ('hid.' + role)
            for key, value in dict(report_length=length, subclass=int(role == 'keyboard'),
                                   protocol=int(role == 'keyboard'), no_out_endpoint=1).items():
                put(fn / key, str(value))
            put(fn / 'report_desc', role)
            put(desc / role, role)
            number = '251:' + str(minor)
            put(fn / 'dev', number)
            identity = sysroot / 'devices/virtual/hidg' / ('hidg' + str(minor))
            put(identity / 'dev', number)
            chars = sysroot / 'dev/char'; chars.mkdir(parents=True, exist_ok=True)
            (chars / number).symlink_to(identity)
            node = devroot / identity.name; put(node, '')
            numbers[node] = os.makedev(251, minor)
            (gadget / 'configs/c.1' / fn.name).symlink_to(fn)
        put(devroot / 'hidg0', 'unrelated')
        return gadget, sysroot, devroot, desc, numbers

    def check(self, args, numbers):
        original = Path.lstat
        def lstat(path):
            if path in numbers:
                return SimpleNamespace(st_mode=stat.S_IFCHR | 0o600, st_rdev=numbers[path])
            return original(path)
        with patch.object(Path, 'lstat', lstat):
            return RESOLVE(*args)

    def test_permuted_numbers_resolve_only_accepted_functions(self):
        with tempfile.TemporaryDirectory() as d:
            *args, numbers = self.fixture(Path(d))
            rows = self.check(args, numbers)
            self.assertEqual([x['dev'] for x in rows], ['251:9', '251:2', '251:6'])
            self.assertNotIn(str(args[2] / 'hidg0'), [x['node'] for x in rows])

    def test_wrong_device_number_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            *args, numbers = self.fixture(Path(d))
            numbers[args[2] / 'hidg9'] = os.makedev(251, 0)
            with self.assertRaisesRegex(RuntimeError, 'character device identity'):
                self.check(args, numbers)

    def test_descriptor_change_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            *args, numbers = self.fixture(Path(d))
            (args[0] / 'functions/hid.absolute/report_desc').write_bytes(b'changed')
            with self.assertRaisesRegex(RuntimeError, 'descriptor mismatch'):
                self.check(args, numbers)

    def test_extra_function_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            *args, numbers = self.fixture(Path(d))
            (args[0] / 'functions/hid.extra').mkdir()
            with self.assertRaisesRegex(RuntimeError, 'function layout'):
                self.check(args, numbers)
