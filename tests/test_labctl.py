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
INITRAMFS_LSUSB = REPOSITORY_ROOT / "initramfs" / "lsusb"
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
    def test_password_prompt_allows_uart_flush_whitespace(self) -> None:
        prompt = LABCTL_MODULE["PASSWORD_PROMPT"]
        self.assertIsNotNone(prompt.search("blikvm\n Password: "))
        self.assertIsNotNone(prompt.search("\nPassword: "))
        self.assertIsNone(prompt.search("echo Password: "))

    def test_uart_line_uses_one_terminator_and_neutral_flush_byte(self) -> None:
        console_type = LABCTL_MODULE["SerialConsole"]
        console = object.__new__(console_type)
        writes: list[tuple[bytes, bool]] = []
        console.write = lambda data, log=True: writes.append((data, log))

        console.write_line(b"version")

        self.assertEqual(writes, [(b"version\r ", True)])
        with self.assertRaises(ValueError):
            console.write_line(b"version\r")

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

        self.assertEqual(
            classify("MS2131 absent", "usb_ms2131_enumeration"),
            "ms2131_not_enumerated",
        )
        self.assertEqual(
            classify("regulator disabled", "usb_vbus_power"),
            "usb_regulator_vbus_or_gpio_failure",
        )

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

    def test_parse_ip_link_interfaces_excludes_loopback(self) -> None:
        parse_interfaces = LABCTL_MODULE["parse_ip_link_interfaces"]
        listing = (
            "1: lo: <LOOPBACK,UP,LOWER_UP> mtu 65536 state UNKNOWN\n"
            "2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 state UP\n"
        )

        self.assertEqual(parse_interfaces(listing), ["eth0"])

    def test_ethernet_evidence_requires_phy_zero_carrier_address_and_ping(self) -> None:
        assess = LABCTL_MODULE["assess_ethernet_evidence"]
        evidence = {
            "ethernet-dmesg.log": (
                "dwmac-sun8i 5030000.ethernet: PTP uses main clock\n"
                "dwmac-sun8i 5030000.ethernet eth0: "
                "PHY [stmmac-0:00] driver [Generic PHY]\n"
                "dwmac-sun8i 5030000.ethernet eth0: "
                "Link is Up - 100Mbps/Full\n"
            ),
            "phy-mdio.log": (
                "mdio_bus=stmmac-0\nphy_device=stmmac-0:00\n"
                "phy_address=00\nphy_id=0x00441400\n"
            ),
            "carrier-state.log": "carrier=1\n",
            "ip-link.log": "2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP>\n",
            "ip-addr.log": "inet 192.168.88.2/24 scope global eth0\n",
            "ip-route.log": (
                "192.168.88.0/24 dev eth0 scope link\ndefault_route_present=0\n"
            ),
            "ping.log": "5 packets transmitted, 5 packets received, 0% packet loss\n",
        }
        statuses = {
            "phy-mdio.log": 0,
            "carrier-state.log": 0,
            "ip-addr.log": 0,
            "ip-route.log": 0,
            "ping.log": 0,
            "ethernet-dmesg.log": 0,
        }

        checks, failed_stage = assess("eth0", statuses, evidence)

        self.assertIsNone(failed_stage)
        self.assertTrue(all(item["status"] == "pass" for item in checks.values()))

        evidence["ping.log"] = (
            "5 packets transmitted, 0 packets received, 100% packet loss\n"
        )
        checks, failed_stage = assess("eth0", statuses, evidence)
        self.assertEqual(checks["ping"]["status"], "fail")
        self.assertEqual(failed_stage, "ping")

    def test_usb_evidence_requires_only_ehci1_and_direct_480m_ms2131(self) -> None:
        assess = LABCTL_MODULE["assess_usb_evidence"]
        evidence = {
            "usb-controller-phy.log": (
                "controller_present=1\ncontroller_driver=ehci-platform\n"
                "phy_present=1\nphy_driver=sun4i-usb-phy\n"
                "enabled_usb_controller=5200000.usb driver=ehci-platform\n"
                "regulator_present=1\nregulator_name=usb1-vbus\n"
                "regulator_state=enabled\n"
            ),
            "usb-enumeration-wait.log": (
                "device=1-1\nvid_pid=345f:2131\nspeed=480\n"
            ),
            "lsusb.log": (
                "Bus 001 Device 002: ID 345f:2131 MACROSILICON USB2 Video\n"
                "Bus 001 Device 001: ID 1d6b:0002 Linux EHCI Host Controller\n"
            ),
            "lsusb-tree.log": (
                "/:  Bus 01.Port 1: Dev 1, Class=root_hub, "
                "Driver=ehci-platform/1p, 480M\n"
                "    |__ Port 1: Dev 2, If 0, Class=Video, Driver=uvcvideo, "
                "480M, ID=345f:2131\n"
                "    |__ Port 1: Dev 2, If 1, Class=Video, Driver=uvcvideo, "
                "480M, ID=345f:2131\n"
                "    |__ Port 1: Dev 2, If 2, Class=Audio, Driver=[none], "
                "480M, ID=345f:2131\n"
                "    |__ Port 1: Dev 2, If 3, Class=Audio, Driver=[none], "
                "480M, ID=345f:2131\n"
                "    |__ Port 1: Dev 2, If 4, Class=Human Interface Device, "
                "Driver=[none], 480M, ID=345f:2131\n"
            ),
            "usb-dmesg.log": (
                "ehci-platform 5200000.usb: EHCI Host Controller\n"
                "ehci-platform 5200000.usb: USB 2.0 started, EHCI 1.00\n"
            ),
        }
        statuses = {name: 0 for name in evidence}

        checks, failed_stage = assess(statuses, evidence)

        self.assertIsNone(failed_stage)
        self.assertTrue(all(item["status"] == "pass" for item in checks.values()))

        evidence["usb-controller-phy.log"] += (
            "enabled_usb_controller=5310000.usb driver=ehci-platform\n"
        )
        checks, failed_stage = assess(statuses, evidence)
        self.assertEqual(checks["controller_probe"]["status"], "fail")
        self.assertEqual(failed_stage, "controller_probe")

        evidence["usb-controller-phy.log"] = evidence["usb-controller-phy.log"].replace(
            "enabled_usb_controller=5310000.usb driver=ehci-platform\n", ""
        ).replace(
            "enabled_usb_controller=5200000.usb driver=ehci-platform\n",
            "enabled_usb_controller=5100000.usb driver=musb-sunxi\n"
            "enabled_usb_controller=5200000.usb driver=ehci-platform\n",
        )
        self.assertEqual(assess(statuses, evidence)[1], "controller_probe")
        self.assertIsNone(assess(statuses, evidence, expect_musb=True)[1])

    def test_uvc_evidence_requires_binding_modes_and_changing_payloads(self) -> None:
        assess = LABCTL_MODULE["assess_uvc_evidence"]
        interface_lines = "\n".join(
            [
                "INTERFACE usb_device=1-1 interface=1-1:1.0 number=00 "
                "class=0e subclass=01 protocol=00 alt=00 endpoints=1 driver=uvcvideo",
                "INTERFACE usb_device=1-1 interface=1-1:1.1 number=01 "
                "class=0e subclass=02 protocol=00 alt=00 endpoints=0 driver=uvcvideo",
                "INTERFACE usb_device=1-1 interface=1-1:1.2 number=02 "
                "class=01 subclass=01 protocol=00 alt=00 endpoints=0 driver=[none]",
                "INTERFACE usb_device=1-1 interface=1-1:1.3 number=03 "
                "class=01 subclass=02 protocol=00 alt=00 endpoints=1 driver=[none]",
                "INTERFACE usb_device=1-1 interface=1-1:1.4 number=04 "
                "class=03 subclass=00 protocol=00 alt=00 endpoints=1 driver=[none]",
            ]
        )
        node_map = (
            "VIDEO_NODE device=/dev/video0 name=USB2_Video dev=81:0 index=0 "
            "sysfs_device=/sys/devices/1-1:1.0/video4linux/video0 "
            "usb_device=1-1 usb_interface=1-1:1.0 interface_number=00 "
            "driver=uvcvideo\n"
            "VIDEO_NODE device=/dev/video1 name=USB2_Video dev=81:1 index=1 "
            "sysfs_device=/sys/devices/1-1:1.0/video4linux/video1 "
            "usb_device=1-1 usb_interface=1-1:1.0 interface_number=00 "
            "driver=uvcvideo\n"
        )
        capabilities = (
            "NODE device=/dev/video0 driver=uvcvideo card=USB2_Video "
            "bus_info=usb-5200000.usb-1 version=7.2.3 capabilities=0x1 "
            "device_caps=0x1 capture=1 metadata=0 streaming=1\n"
            "NODE device=/dev/video1 driver=uvcvideo card=USB2_Video "
            "bus_info=usb-5200000.usb-1 version=7.2.3 capabilities=0x1 "
            "device_caps=0x1 capture=0 metadata=1 streaming=1\n"
            "INPUT device=/dev/video0 index=0 current=1 name=Camera type=2 "
            "status=0x00000000 capabilities=0x00000000 std=0x0\n"
            "STANDARDS device=/dev/video0 applicable=0 count=0\n"
            "FORMAT device=/dev/video0 type=video_capture index=0 fourcc=YUYV "
            "flags=0x0 description=YUYV_4:2:2\n"
            "SIZE device=/dev/video0 fourcc=YUYV index=0 kind=discrete "
            "width=640 height=480\n"
            "INTERVAL device=/dev/video0 fourcc=YUYV width=640 height=480 "
            "index=0 kind=discrete numerator=1 denominator=30 fps=30.000\n"
            "ENUMERATION_SUMMARY result=pass nodes=2 capture_nodes=1 "
            "metadata_nodes=1 formats=2 sizes=1 intervals=1 inputs=1 standards=0\n"
        )
        frames = []
        for index in range(60):
            frames.append(
                f"FRAME index={index} sequence={index} bytesused=614400 "
                f"nonzero_bytes=600000 hash_fnv1a64={index + 1:016x} "
                f"changed_from_previous={int(index > 0)} timestamp=1.000000 "
                "flags=0x00000000"
            )
        stream = (
            "CAPTURE_CONFIG device=/dev/video0 requested_fourcc=YUYV "
            "requested_width=640 requested_height=480 requested_fps=30 "
            "negotiated_fourcc=YUYV negotiated_width=640 negotiated_height=480 "
            "interval=1/30 bytesperline=1280 sizeimage=614400 field=1\n"
            + "\n".join(frames)
            + "\nCAPTURE_SUMMARY result=pass device=/dev/video0 frames=60 "
            "nonempty_frames=60 changing_transitions=59 unique_hashes=60 "
            "total_bytes=36864000 total_nonzero_bytes=36000000 "
            "startup_error_frames=0 error_frames=0\n"
        )
        evidence = {
            "console-loglevel.log": "console_loglevel=1\n",
            "uvc-detection.log": "vid_pid=345f:2131\nuvc_interfaces=2\nvideo_nodes=2\n",
            "usb-interface-bindings.log": interface_lines,
            "video-node-map.log": node_map,
            "v4l2-capabilities.log": capabilities,
            "v4l2-stream.log": stream,
            "uvc-dmesg.log": (
                "usb 1-1: New USB device found, idVendor=345f, idProduct=2131\n"
                "usbcore: registered new interface driver uvcvideo\n"
            ),
            "console-loglevel-restore.log": "console_loglevel=8\n",
        }
        statuses = {name: 0 for name in evidence}

        checks, failed_stage, parsed = assess(statuses, evidence)

        self.assertIsNone(failed_stage)
        self.assertTrue(all(item["status"] == "pass" for item in checks.values()))
        self.assertEqual(checks["format_enumeration"]["formats"], ["YUYV"])
        self.assertEqual(parsed["capture_summary"]["unique_hashes"], "60")

        startup_discard_stream = stream.replace(
            "CAPTURE_CONFIG device=",
            "FRAME_DISCARD phase=startup reason=error_flag sequence=0 "
            "bytesused=2425 timestamp=1.000000 flags=0x00000040\n"
            "CAPTURE_CONFIG device=",
        ).replace("startup_error_frames=0", "startup_error_frames=1")
        evidence["v4l2-stream.log"] = startup_discard_stream
        checks, failed_stage, _parsed = assess(statuses, evidence)
        self.assertIsNone(failed_stage)
        self.assertEqual(checks["bounded_stream"]["startup_error_frames"], 1)

        evidence["v4l2-stream.log"] = stream.replace(
            "startup_error_frames=0 error_frames=0",
            "startup_error_frames=0 error_frames=1",
        )
        checks, failed_stage, _parsed = assess(statuses, evidence)
        self.assertEqual(checks["bounded_stream"]["status"], "fail")
        self.assertEqual(failed_stage, "bounded_stream")

        unchanged_stream = stream
        for index in range(1, 60):
            unchanged_stream = unchanged_stream.replace(
                f"hash_fnv1a64={index + 1:016x}",
                "hash_fnv1a64=0000000000000001",
            )
        unchanged_stream = unchanged_stream.replace(
            "changing_transitions=59 unique_hashes=60",
            "changing_transitions=0 unique_hashes=1",
        )
        evidence["v4l2-stream.log"] = unchanged_stream
        checks, failed_stage, _parsed = assess(statuses, evidence)
        self.assertEqual(checks["changing_frames"]["status"], "fail")
        self.assertEqual(failed_stage, "changing_frames")

    def test_initramfs_lsusb_reports_flat_identity_and_tree(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            sys_root = Path(temporary) / "sys"
            devices = sys_root / "bus" / "usb" / "devices"
            root = devices / "usb1"
            capture = devices / "1-1"
            interface = devices / "1-1:1.0"
            values = {
                root: {
                    "idVendor": "1d6b",
                    "idProduct": "0002",
                    "manufacturer": "Linux 7.2.3 ehci_hcd",
                    "product": "EHCI Host Controller",
                    "busnum": "1",
                    "devnum": "1",
                    "maxchild": "1",
                    "speed": "480",
                },
                capture: {
                    "idVendor": "345f",
                    "idProduct": "2131",
                    "manufacturer": "MACROSILICON",
                    "product": "USB2 Video",
                    "busnum": "1",
                    "devnum": "2",
                    "devpath": "1",
                    "speed": "480",
                },
                interface: {
                    "bInterfaceNumber": "00",
                    "bInterfaceClass": "0e",
                },
            }
            for directory, attributes in values.items():
                for name, value in attributes.items():
                    write_value(directory / name, value)
            (root / "controller-driver").symlink_to("/drivers/ehci-platform")
            environment = os.environ.copy()
            environment["LSUSB_SYS_ROOT"] = str(sys_root)

            flat = subprocess.run(
                ["/bin/sh", str(INITRAMFS_LSUSB)],
                env=environment,
                check=True,
                capture_output=True,
                text=True,
            ).stdout
            tree = subprocess.run(
                ["/bin/sh", str(INITRAMFS_LSUSB), "-t"],
                env=environment,
                check=True,
                capture_output=True,
                text=True,
            ).stdout

            self.assertIn("ID 345f:2131 MACROSILICON USB2 Video", flat)
            self.assertIn("Driver=ehci-platform/1p, 480M", tree)
            self.assertIn(
                "Port 1: Dev 2, If 0, Class=Video, Driver=[none], "
                "480M, ID=345f:2131",
                tree,
            )

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

    def test_uart_resolution_falls_back_to_unique_usb_identity_tty(self) -> None:
        resolve = LABCTL_MODULE["resolve_uart_device"]
        fixture = LabctlDetectTests()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            sys_root = root / "sys"
            dev_root = root / "dev"
            dev_root.mkdir()
            fixture.add_usb(sys_root, "1-2", "1a86:7523", "USB Serial")
            fixture.add_uart(sys_root, dev_root)
            (dev_root / "serial" / "by-id" / "usb-1a86_USB_Serial-if00-port0").unlink()

            self.assertEqual(
                resolve(sys_root, dev_root, None), dev_root / "ttyUSB0"
            )


if __name__ == "__main__":
    unittest.main()
