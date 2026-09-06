import json
from pathlib import Path
import runpy
import tempfile
import unittest

HID = runpy.run_path(str(Path(__file__).resolve().parents[1] / "lab/hidlab.py"))


class HostHIDTests(unittest.TestCase):
    def make_device(self, root, name="1-3"):
        p = root / name
        p.mkdir()
        for key, value in {"idVendor": "1d6b", "idProduct": "0106",
                           "serial": HID["SERIAL"], "speed": "480", "devnum": "8"}.items():
            (p / key).write_text(value)
        interface = root / (name + ":1.0")
        interface.mkdir()
        for key, value in {"bInterfaceClass": "03", "bInterfaceSubClass": "01",
                           "bInterfaceProtocol": "01"}.items():
            (interface / key).write_text(value)
        (interface / "driver").symlink_to("/drivers/usbhid")
        return p

    def test_identity_and_exact_keyboard_interface(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            p = self.make_device(root)
            self.assertEqual(HID["keyboard_device"](root), p)
            self.assertTrue(HID["keyboard_details"](p)["passed"])
            extra = root / "1-3:1.1"
            extra.mkdir()
            self.assertFalse(HID["keyboard_details"](p)["passed"])
            (p / "serial").write_text("vendor-device")
            self.assertIsNone(HID["keyboard_device"](root))

    def test_duplicate_identity_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.make_device(root)
            self.make_device(root, "1-4")
            with self.assertRaisesRegex(RuntimeError, "ambiguous"):
                HID["keyboard_device"](root)

    def test_reconnect_evidence_requires_same_artifacts_and_pass(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            report = root / "test-results.json"
            report.write_text(json.dumps({"result": "passed", "run_id": "first",
                                         "hid": {"physical_reconnect": {"passed": True}}}))
            (root / "metadata.json").write_text(json.dumps({"artifacts": {"Image": "hash"}}))
            self.assertTrue(HID["prior_reconnect"](report, {"Image": "hash"})["passed"])
            with self.assertRaises(RuntimeError):
                HID["prior_reconnect"](report, {"Image": "changed"})
            report.write_text('{"result":"failed"}')
            with self.assertRaises(RuntimeError):
                HID["prior_reconnect"](report, {"Image": "hash"})

class InputEventTests(unittest.TestCase):
    def events(self, keys):
        out = []
        for code, value in keys:
            out.extend([{'type': 1, 'code': code, 'value': value},
                        {'type': 0, 'code': 0, 'value': 0}])
        return out

    def test_press_and_release_required_in_order(self):
        assess = HID['assess_shift']
        self.assertTrue(assess(self.events([(42, 1), (42, 0)]))['passed'])
        for keys in [[(42, 1)], [(42, 0)], [(42, 0), (42, 1)],
                     [(30, 1), (30, 0)], [(42, 1), (42, 2), (42, 0)]]:
            with self.assertRaises(RuntimeError):
                assess(self.events(keys))

    def test_native_input_record_and_truncation(self):
        data = HID['INPUT_EVENT'].pack(123, 456, 1, 42, 1)
        self.assertEqual(HID['decode_input'](data)[0],
                         {'seconds': 123, 'microseconds': 456,
                          'type': 1, 'code': 42, 'value': 1})
        with self.assertRaises(RuntimeError):
            HID['decode_input'](data[:-1])
