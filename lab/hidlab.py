"""Bridge-side qualification of the RAM-only M5 keyboard slice."""

from __future__ import annotations

import json
import fcntl
import struct
import shlex
import re
import os
from pathlib import Path
import select
import subprocess
import sys
import time


SERIAL = "blikvm-v4-m5-keyboard"
REPORT_DESCRIPTOR = bytes.fromhex(
    "05010906a101050719e029e715002501750195088102950175088101"
    "9505750105081901290591029501750391019506750815002565"
    "0507190029658100c0"
)


def read(path):
    try:
        return path.read_text().strip()
    except OSError:
        return ""


def keyboard_device(root=Path("/sys/bus/usb/devices")):
    matches = [p for p in root.iterdir()
               if read(p / "idVendor") == "1d6b"
               and read(p / "idProduct") == "0106"
               and read(p / "serial") == SERIAL]
    if len(matches) > 1:
        raise RuntimeError("ambiguous M5 keyboard identity")
    return matches[0] if matches else None


def keyboard_details(device):
    interfaces = sorted(device.parent.glob(device.name + ":*"))
    records = [{"name": p.name,
                "class": read(p / "bInterfaceClass"),
                "subclass": read(p / "bInterfaceSubClass"),
                "protocol": read(p / "bInterfaceProtocol"),
                "driver": (p / "driver").resolve().name if (p / "driver").is_symlink() else ""}
               for p in interfaces]
    valid = (read(device / "speed") == "480" and len(records) == 1
             and records[0]["class"] == "03"
             and records[0]["subclass"] == "01"
             and records[0]["protocol"] == "01"
             and records[0]["driver"] == "usbhid")
    return {"passed": valid, "device": device.name,
            "serial": read(device / "serial"), "speed": read(device / "speed"),
            "interfaces": records, "device_number": read(device / "devnum")}


def wait_keyboard(present, timeout):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        device = keyboard_device()
        if not present and device is None:
            return None
        if present and device is not None and keyboard_details(device)["passed"]:
            return device
        time.sleep(0.1)
    raise TimeoutError("host keyboard did not " + ("enumerate" if present else "disconnect"))


def raw_keyboard(device):
    parent = device.resolve()
    matches = [p for p in Path("/sys/class/hidraw").glob("hidraw*")
               if parent in (p / "device").resolve().parents]
    if len(matches) != 1:
        raise RuntimeError("expected one hidraw node for the exact M5 keyboard")
    descriptor = (matches[0] / "device/report_descriptor").read_bytes()
    if descriptor != REPORT_DESCRIPTOR:
        raise RuntimeError("host keyboard report descriptor differs from target definition")
    return Path("/dev") / matches[0].name


# Linux input_event uses native timeval layout on the bridge.
INPUT_EVENT = struct.Struct("@llHHi")


def input_keyboard(device):
    nodes = [p for p in Path("/sys/class/input").glob("event*")
             if device.resolve() in (p / "device").resolve().parents]
    if len(nodes) != 1:
        raise RuntimeError("expected one evdev node for the exact M5 keyboard")
    p = nodes[0]
    identity = {"node": "/dev/input/" + p.name,
                "sysfs": str((p / "device").resolve()),
                **{a: read(p / "device" / a) for a in
                   ("name", "phys", "uniq", "id/vendor", "id/product", "capabilities/key")}}
    if identity["id/vendor"] != "1d6b" or identity["id/product"] != "0106":
        raise RuntimeError("evdev identity mismatch")
    return identity


def decode_input(data):
    if len(data) % INPUT_EVENT.size:
        raise RuntimeError("truncated input_event record")
    return [{"seconds": sec, "microseconds": usec, "type": typ,
             "code": code, "value": value}
            for sec, usec, typ, code, value in INPUT_EVENT.iter_unpack(data)]


def assess_shift(events):
    keys = [(e["code"], e["value"]) for e in events if e["type"] == 1]
    if keys != [(42, 1), (42, 0)]:
        raise RuntimeError("expected exactly KEY_LEFTSHIFT press then release: " + str(keys))
    if sum(e["type"] == 0 and e["code"] == 0 for e in events) < 2:
        raise RuntimeError("missing input synchronization events")
    return {"passed": True, "key": "KEY_LEFTSHIFT", "code": 42,
            "press_verified": True, "release_verified": True}


def modifier_command():
    # A bounded writer with an EXIT trap releases the modifier even on error.
    script = r'''set -e; dev=$(cat /sys/kernel/config/usb_gadget/blikvm_m5/functions/hid.keyboard/dev); path=$(readlink -f "/sys/dev/char/$dev"); node=/dev/${path##*/}; [ -c "$node" ]; trap 'hid-keyboard report' EXIT; printf '\002\000\000\000\000\000\000\000' > "$node"; sleep 0.15; hid-keyboard report; trap - EXIT'''
    return "timeout 5 sh -c " + shlex.quote(script)


class InputCapture:
    def __init__(self, device, recorder):
        self.identity = input_keyboard(device)
        self.recorder = recorder
        self.fd = None

    def __enter__(self):
        self.fd = os.open(self.identity["node"], os.O_RDONLY | os.O_NONBLOCK)
        try:
            # Keep the harmless test modifier private to this verifier.
            fcntl.ioctl(self.fd, 0x40044590, 1)  # EVIOCGRAB
            while select.select([self.fd], [], [], 0)[0]:
                os.read(self.fd, 4096)
        except BaseException:
            os.close(self.fd)
            self.fd = None
            raise
        return self

    def verify(self, suffix):
        data = b""
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            if select.select([self.fd], [], [], 0.2)[0]:
                data += os.read(self.fd, INPUT_EVENT.size * 64)
            elif data:
                break
        events = decode_input(data)
        self.recorder.save_text("host-input-" + suffix + ".json",
                                json.dumps({"identity": self.identity, "events": events}, indent=2))
        return {**assess_shift(events), "identity": self.identity, "events": events}

    def __exit__(self, *args):
        if self.fd is not None:
            try:
                fcntl.ioctl(self.fd, 0x40044590, 0)
            finally:
                os.close(self.fd)


def usb_errors(text):
    return [line for line in text.splitlines()
            if re.search(r"usb|musb|phy|udc|hid|xhci|uvc", line, re.I)
            and re.search(r"\berror\b|\bfailed\b|timed out|\btimeout\b|babble|over.current|\bstall\b|BUG:|Oops", line, re.I)]


class HostMonitor:
    def __init__(self, recorder):
        self.recorder = recorder
        self.processes = []
        self.files = []

    def start(self):
        for name, command in (
            ("host-udev-events.log", ["stdbuf", "-oL", "udevadm", "monitor", "--kernel", "--udev", "--property"]),
            ("host-kernel-live.log", ["dmesg", "--follow-new", "--time-format", "iso"]),
        ):
            stream = (self.recorder.path / name).open("w")
            self.files.append(stream)
            self.processes.append(subprocess.Popen(command, stdout=stream, stderr=subprocess.STDOUT))
        time.sleep(0.3)
        if any(p.poll() is not None for p in self.processes):
            raise RuntimeError("host event monitor failed to start")

    def stop(self):
        for p in self.processes:
            p.terminate()
            try:
                p.wait(5)
            except subprocess.TimeoutExpired:
                p.kill()
                p.wait()
        for stream in self.files:
            stream.close()


def host_logs(recorder, suffix):
    for name, command in (
        ("lsusb", ["lsusb"]), ("lsusb-tree", ["lsusb", "-t"]),
        ("descriptors", ["lsusb", "-v", "-d", "1d6b:0106"]),
        ("dmesg", ["dmesg"]),
    ):
        p = subprocess.run(command, capture_output=True, text=True, timeout=15)
        recorder.save_text(f"host-{name}-{suffix}.log", p.stdout + p.stderr)
        if p.returncode and not (name == "descriptors" and suffix == "before" and p.returncode == 1):
            raise RuntimeError("host evidence command failed: " + " ".join(command))


def prior_reconnect(path, artifacts):
    report = json.loads(path.read_text())
    metadata = json.loads(path.with_name("metadata.json").read_text())
    if (report.get("result") != "passed"
            or not report.get("hid", {}).get("physical_reconnect", {}).get("passed")
            or metadata.get("artifacts") != artifacts):
        raise RuntimeError("prior reconnect evidence must pass with identical artifacts")
    return {"passed": True, "evidence_run": report["run_id"], "repeated_this_boot": False}


def run_hid_test(console, recorder, args, run_uvc_test, capture):
    result = {"result": "failed", "failed_stage": "udc", "error": "incomplete"}
    stage = "udc"
    raw_fd = None
    monitor = HostMonitor(recorder)

    def target(name, command):
        rc, output = capture(console, recorder, name + ".log", name.replace("-", "_"), command, 20)
        if rc:
            raise RuntimeError(f"{name}: target command exited {rc}")
        return output

    try:
        monitor.start()
        host_logs(recorder, "before")
        target("hid-console-quiet", "echo N > /sys/module/printk/parameters/ignore_loglevel; dmesg -n 1")
        target("udc-before", "hid-keyboard state")
        stage = "configfs"
        target("hid-setup", "hid-keyboard setup")
        stage = "enumeration"
        target("hid-bind", "hid-keyboard bind")
        device = wait_keyboard(True, 15)
        result["enumeration"] = keyboard_details(device)
        target("hid-state-bound", "hid-keyboard state")
        host_logs(recorder, "bound")
        stage = "unbind_rebind"
        old_number = read(device / "devnum")
        target("hid-unbind", "hid-keyboard unbind")
        wait_keyboard(False, 10)
        target("hid-state-unbound", "hid-keyboard state")
        target("hid-rebind", "hid-keyboard bind")
        device = wait_keyboard(True, 15)
        if read(device / "devnum") == old_number:
            raise RuntimeError("USB device number did not change after rebind")
        result["unbind_rebind"] = {"passed": True, "before": old_number,
                                   "after": read(device / "devnum")}
        stage = "physical_reconnect"
        if args.reconnect_evidence:
            result["physical_reconnect"] = prior_reconnect(
                args.reconnect_evidence, recorder.metadata["artifacts"])
        else:
            print(f"HID_RECONNECT_READY run={recorder.run_id}; unplug USB-PC only, wait 2 seconds, reconnect", file=sys.stderr, flush=True)
            old_number = read(device / "devnum")
            wait_keyboard(False, args.reconnect_timeout)
            disconnected_at = time.time()
            device = wait_keyboard(True, args.reconnect_timeout)
            if read(device / "devnum") == old_number:
                raise RuntimeError("USB device number unchanged after physical reconnect")
            result["physical_reconnect"] = {"passed": True, "repeated_this_boot": True,
                                             "disconnected_at": disconnected_at,
                                             "reconnected_at": time.time()}
        target("hid-state-reconnected", "hid-keyboard state")
        stage = "report_and_uvc"
        raw_path = raw_keyboard(device)
        recorder.save_text("host-report-descriptor.hex", REPORT_DESCRIPTOR.hex() + "\n")
        with InputCapture(device, recorder) as input_capture:
            try:
                target("hid-modifier-report", modifier_command())
            finally:
                target("hid-emergency-release", "hid-keyboard report")
            result["input_report"] = input_capture.verify("report")
        with InputCapture(device, recorder) as input_capture:
            try:
                result["uvc"] = run_uvc_test(console, recorder, concurrent_hid=True,
                                              hid_report_command=modifier_command())
            finally:
                target("hid-concurrent-release", "hid-keyboard report")
            result["concurrent_input_report"] = input_capture.verify("concurrent-report")
        if result["uvc"]["result"] != "passed":
            raise RuntimeError("concurrent UVC failed: " + str(result["uvc"]["failed_stage"]))
        state = target("hid-state-after-uvc", "hid-keyboard state")
        if "state=configured" not in state:
            raise RuntimeError("UDC not configured after UVC capture")
        if not keyboard_details(wait_keyboard(True, 5))["passed"]:
            raise RuntimeError("keyboard lost after UVC capture")
        target_log = target("hid-dmesg-after", "dmesg")
        monitor.stop()
        errors = usb_errors(target_log) + usb_errors(read(recorder.path / "host-kernel-live.log"))
        result["usb_errors"] = {"passed": not errors, "matching_lines": errors}
        if errors:
            raise RuntimeError("USB/HID/controller errors observed: " + str(errors))
        host_logs(recorder, "after")
        result.update(result="passed", failed_stage=None, error=None)
    except Exception as error:
        result.update(result="failed", failed_stage=stage, error=str(error))
    finally:
        monitor.stop()
        if raw_fd is not None:
            os.close(raw_fd)
        try:
            target("hid-final-state", "dmesg; hid-keyboard state")
            target("hid-console-restore", "dmesg -n 8; echo Y > /sys/module/printk/parameters/ignore_loglevel")
        except Exception as error:
            result["final_collection_error"] = str(error)
            if result["result"] == "passed":
                result.update(result="failed", failed_stage="collect", error=str(error))
    return result
