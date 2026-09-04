from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import runpy
import subprocess
import sys
import tempfile
import unittest


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
LABCTL = REPOSITORY_ROOT / "lab" / "labctl"
LABCTL_MODULE = runpy.run_path(str(LABCTL), run_name="labctl_test_module")


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


class LabctlAutomationTests(unittest.TestCase):
    def test_console_cleanup_and_environment_parsing(self) -> None:
        clean_console = LABCTL_MODULE["clean_console"]
        parse_environment = LABCTL_MODULE["parse_environment"]
        raw = b"\x1b[32mkernel_addr_r=0x40080000\x1b[0m\r\nnot a key=x\r\n=> "

        cleaned = clean_console(raw)

        self.assertNotIn("\x1b", cleaned)
        self.assertEqual(
            parse_environment(cleaned), {"kernel_addr_r": "0x40080000"}
        )

    def test_forbids_persistent_or_media_writing_uboot_commands(self) -> None:
        session_type = LABCTL_MODULE["UBootSession"]
        session = session_type(None, None)

        for command in (
            "saveenv",
            "env save",
            "mmc write 0x40000000 0 1",
            "sf erase 0 1000",
            "fatwrite mmc 0:1 0x40000000 forbidden 10",
            "ext4write mmc 0:1 0x40000000 /forbidden 10",
        ):
            with self.subTest(command=command):
                with self.assertRaisesRegex(ValueError, "refusing"):
                    session.execute(command)

    def test_vendor_manifest_hashes_exact_artifacts(self) -> None:
        vendor_manifest = LABCTL_MODULE["vendor_manifest"]
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "Image").write_bytes(b"kernel")
            (root / "uInitrd").write_bytes(b"ramdisk")
            (root / "sun50i-h616-mangopi-mcore.dtb").write_bytes(b"fdt")

            manifest = vendor_manifest(root)

            self.assertEqual(manifest["kernel"]["size"], 6)
            self.assertEqual(
                manifest["kernel"]["sha256"],
                "6923dd1bc0460082c5d55a831908c24a282860b7f1cd6c2b79cf1bc8857c639c",
            )

    def test_linux_manifest_rejects_an_artifact_changed_after_build(self) -> None:
        linux_artifact_manifest = LABCTL_MODULE["linux_artifact_manifest"]
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            payloads = {
                "Image": b"arm64 kernel",
                "sun50i-h616-blikvm-v4.dtb": b"device tree",
                "initramfs.cpio.gz": b"initramfs",
                "linux.config": b"CONFIG_ARCH_SUNXI=y\n",
            }
            records = {}
            for name, payload in payloads.items():
                (root / name).write_bytes(payload)
                records[name] = {
                    "name": name,
                    "size": len(payload),
                    "sha256": hashlib.sha256(payload).hexdigest(),
                }
            (root / "manifest.json").write_text(
                json.dumps(
                    {
                        "linux": {"version": "7.2.3"},
                        "initramfs": {"ready_marker": "BLIKVM_INITRAMFS_READY"},
                        "build": {},
                        "artifacts": records,
                    }
                ),
                encoding="utf-8",
            )

            self.assertEqual(linux_artifact_manifest(root)["linux"]["version"], "7.2.3")
            (root / "Image").write_bytes(b"changed")
            with self.assertRaisesRegex(RuntimeError, "does not match manifest"):
                linux_artifact_manifest(root)

    def test_boot_failure_classifier_uses_uart_evidence(self) -> None:
        classify = LABCTL_MODULE["classify_boot_failure"]
        cases = {
            "Failed to execute /init (error -8)": "init_not_executable",
            "Kernel panic - not syncing: VFS: Unable to mount root fs": (
                "unable_to_mount_initramfs"
            ),
            "Starting kernel ...": "kernel_console_timeout",
        }
        for text, expected in cases.items():
            with self.subTest(text=text):
                self.assertEqual(classify(text, "kernel_boot"), expected)

    def test_shell_markers_match_before_a_following_prompt(self) -> None:
        verified = LABCTL_MODULE["SHELL_VERIFIED"]
        dmesg_end = LABCTL_MODULE["DMESG_END"]
        prompt = "blikvm-initramfs:/ # "

        self.assertIsNotNone(
            verified.search(
                "BLIKVM_SHELL_OK kernel=7.2.3-blikvm-v4-serial\n" + prompt
            )
        )
        self.assertIsNotNone(dmesg_end.search("BLIKVM_DMESG_END\n" + prompt))

    def test_mmc_printk_can_tear_initial_shell_prompt(self) -> None:
        prompt = LABCTL_MODULE["INITRAMFS_SHELL"]
        torn = (
            "blikvm-initra[    0.562699] mmcblk0: mmc0:59b4 EC1S5 59.7 GiB\n"
            "mfs:/ # \x1b[6n[    0.569494] mmcblk0: p1 p2 p3\n"
        )

        self.assertIsNone(prompt.search(torn))
        self.assertIsNotNone(prompt.search(torn + "blikvm-initramfs:/ # "))

    def test_tftp_transfer_size_must_match_the_published_artifact(self) -> None:
        parse_tftp_size = LABCTL_MODULE["parse_tftp_size"]

        parse_tftp_size("Bytes transferred = 4096 (1000 hex)", 4096, "Image")
        with self.assertRaisesRegex(RuntimeError, "size mismatch"):
            parse_tftp_size("Bytes transferred = 4095", 4096, "Image")

    def test_parse_mmc_lsblk_identifies_disk_and_partitions(self) -> None:
        parse_mmc_lsblk = LABCTL_MODULE["parse_mmc_lsblk"]
        listing = (
            "NAME\tKNAME\tMAJ:MIN\tRO\tSIZE_SECTORS\tTYPE\tFSTYPE\tMOUNTPOINT\n"
            "mmcblk0\t/dev/mmcblk0\t179:0\t1\t125173760\tdisk\t-\t-\n"
            "mmcblk0p1\t/dev/mmcblk0p1\t179:1\t1\t10695456\tpart\text4\t-\n"
        )

        devices = parse_mmc_lsblk(listing)

        self.assertEqual([item["name"] for item in devices], ["mmcblk0", "mmcblk0p1"])
        self.assertEqual(devices[1]["fstype"], "ext4")
        self.assertEqual(devices[1]["ro"], "1")

    def test_guarded_vendor_phy_workaround_changes_only_verified_field(self) -> None:
        apply_workaround = LABCTL_MODULE["apply_vendor_phy_workaround"]

        class FakeSession:
            def __init__(self) -> None:
                self.commands: list[str] = []

            def execute(self, command: str, _timeout: float) -> str:
                self.commands.append(command)
                if command == "version":
                    return "U-Boot 2021.10-armbian (Feb 20 2023 - 09:48:57 +0800)"
                if command == "bdinfo":
                    return (
                        "-> start    = 0x0000000040000000\n"
                        "-> size     = 0x0000000040000000\n=> "
                    )
                if command.startswith("fdt addr"):
                    return "ethernet-phy@16 {\nreg = <0x00000010>;\n};\n=> "
                if command.startswith("mdio read"):
                    return "2 - 0x44\n3 - 0x1400\n=> "
                if command == "dm uclass":
                    return "0 * ethernet@5030000 @ 7bf43380, seq 0\n=> "
                if command == "md.q 7bf433b8 1":
                    return "7bf433b8: 000000007bf4bb00\n=> "
                if command == "md.l 7bf6cb00 2":
                    return "7bf6cb00: 00000006 00000010\n=> "
                if command == "md.q 7bf6cb40 1":
                    return "7bf6cb40: 000000007bf44620\n=> "
                if command == "md.l 7bf4466c 1":
                    return "7bf4466c: 00000010\n=> "
                if command.startswith("mw.l 7bf4466c 0 1"):
                    return "7bf4466c: 00000000\n=> "
                raise AssertionError(f"unexpected command: {command}")

        session = FakeSession()
        result = apply_workaround(session)

        self.assertTrue(result["applied"])
        self.assertFalse(result["persistent"])
        self.assertEqual(session.commands[-1], "mw.l 7bf4466c 0 1; md.l 7bf4466c 1")


if __name__ == "__main__":
    unittest.main()
