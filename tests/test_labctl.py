from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
LABCTL = REPOSITORY_ROOT / "lab" / "labctl"


def write_value(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value + "\n", encoding="utf-8")


class LabctlDetectTests(unittest.TestCase):
    def run_detect(
        self, sys_root: Path, dev_root: Path, tool_path: str | None = None
    ) -> dict:
        environment = os.environ.copy()
        environment["LABCTL_SYS_ROOT"] = str(sys_root)
        environment["LABCTL_DEV_ROOT"] = str(dev_root)
        command = [str(LABCTL), "detect"]
        if tool_path is not None:
            environment["PATH"] = tool_path
            command = [sys.executable, str(LABCTL), "detect"]
        process = subprocess.run(
            command,
            cwd=REPOSITORY_ROOT,
            env=environment,
            check=True,
            capture_output=True,
            text=True,
        )
        return json.loads(process.stdout)

    def add_usb(
        self,
        sys_root: Path,
        name: str,
        usb_id: str,
        product: str,
        serial: str = "test-serial",
    ) -> None:
        vendor, product_id = usb_id.split(":")
        root = sys_root / "bus" / "usb" / "devices" / name
        write_value(root / "idVendor", vendor)
        write_value(root / "idProduct", product_id)
        write_value(root / "manufacturer", "Fixture Corp")
        write_value(root / "product", product)
        write_value(root / "serial", serial)
        write_value(root / "speed", "480")
        write_value(root / "busnum", "1")
        write_value(root / "devnum", "2")

    def add_uart(self, sys_root: Path, dev_root: Path) -> None:
        tty_target = (
            sys_root
            / "devices"
            / "platform"
            / "usb1"
            / "1-2"
            / "1-2:1.0"
            / "ttyUSB0"
        )
        tty_target.mkdir(parents=True)
        tty_class = sys_root / "class" / "tty"
        tty_class.mkdir(parents=True)
        (tty_class / "ttyUSB0").symlink_to(tty_target)

        (dev_root / "ttyUSB0").touch()
        by_id = dev_root / "serial" / "by-id"
        by_id.mkdir(parents=True)
        (by_id / "usb-1a86_USB_Serial-if00-port0").symlink_to(
            Path("../../ttyUSB0")
        )

    def add_ethernet(self, sys_root: Path, carrier: str = "1") -> None:
        interface = sys_root / "class" / "net" / "enp1s0"
        write_value(interface / "type", "1")
        write_value(interface / "address", "02:00:00:00:00:01")
        write_value(interface / "operstate", "up" if carrier == "1" else "down")
        write_value(interface / "carrier", carrier)
        (interface / "device").mkdir()

    def test_detect_classifies_all_known_usb_roles_and_stable_uart(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            sys_root = root / "sys"
            dev_root = root / "dev"
            dev_root.mkdir()

            self.add_usb(sys_root, "1-2", "1a86:7523", "USB Serial")
            self.add_usb(sys_root, "1-3", "1d6b:0106", "BliKVM Gadget")
            self.add_usb(sys_root, "1-4", "1f3a:efe8", "Allwinner FEL")
            self.add_usb(sys_root, "1-5", "3343:803a", "LattePanda Leonardo")
            self.add_usb(sys_root, "usb1", "1d6b:0002", "Root Hub")
            self.add_uart(sys_root, dev_root)
            self.add_ethernet(sys_root)

            report = self.run_detect(sys_root, dev_root)

            self.assertEqual(report["schema_version"], 1)
            self.assertEqual(report["result"], "ok")
            roles = {item["usb_id"]: item["role"] for item in report["usb_devices"]}
            self.assertEqual(roles["1a86:7523"], "blikvm_uart")
            self.assertEqual(roles["1d6b:0106"], "blikvm_usb_gadget")
            self.assertEqual(roles["1f3a:efe8"], "allwinner_fel")
            self.assertEqual(roles["3343:803a"], "host_lattepanda_mcu")
            self.assertEqual(report["checks"]["blikvm_uart"]["status"], "pass")
            self.assertEqual(report["serial_devices"][0]["role"], "blikvm_uart")
            self.assertEqual(report["serial_devices"][0]["usb_id"], "1a86:7523")
            self.assertEqual(
                report["checks"]["stable_uart_path"]["paths"],
                ["/dev/serial/by-id/usb-1a86_USB_Serial-if00-port0"],
            )
            self.assertEqual(
                report["checks"]["lab_ethernet_carrier"]["status"], "pass"
            )

    def test_missing_sysfs_entries_are_reported_without_crashing(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            sys_root = root / "missing-sys"
            dev_root = root / "missing-dev"
            report = self.run_detect(sys_root, dev_root, tool_path="")

            self.assertEqual(report["result"], "ok")
            self.assertEqual(report["readiness"], "blocked")
            self.assertEqual(report["usb_devices"], [])
            self.assertEqual(report["serial_devices"], [])
            self.assertEqual(report["network_interfaces"], [])
            self.assertEqual(report["checks"]["build_toolchain"]["status"], "missing")
            self.assertTrue(
                any("build prerequisites" in item for item in report["blockers"])
            )
            self.assertGreaterEqual(len(report["blockers"]), 4)
            self.assertFalse(sys_root.exists())
            self.assertFalse(dev_root.exists())

    def test_host_mcu_is_not_treated_as_the_blikvm_uart(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            sys_root = root / "sys"
            dev_root = root / "dev"
            dev_root.mkdir()
            self.add_usb(sys_root, "1-5", "3343:803a", "LattePanda Leonardo")
            self.add_ethernet(sys_root, carrier="0")

            report = self.run_detect(sys_root, dev_root)

            self.assertEqual(report["checks"]["blikvm_uart"]["count"], 0)
            self.assertEqual(report["checks"]["blikvm_uart"]["status"], "missing")
            self.assertEqual(
                report["usb_devices"][0]["role"], "host_lattepanda_mcu"
            )


if __name__ == "__main__":
    unittest.main()
