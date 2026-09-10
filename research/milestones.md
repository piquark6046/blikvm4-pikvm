# Bring-up milestones

Each milestone has an artifact, pass gate, and fallback. A later milestone may not paper over an earlier failure.

## M0 — Tooling and evidence

Build Linux/DT/initramfs in a pinned AMD64 container; implement device detection, UART capture/interrupt, source pinning, and run manifests. **Pass:** `labctl detect` identifies the CH341 UART; a dry build is reproducible; UART captures a complete known-good reboot. **Current:** passed; no-change incremental builds reproduce the artifact hashes and use `-j3` by default.

## M1 — Linux 7.x console

Create the minimal board DTS and config. Boot `Image` + DTB + Alpine initramfs from vendor U-Boot. **Pass:** SPL/U-Boot load succeeds, `earlycon` and ttyS0 work, all four CPUs start, `/init` prints the ready marker, no fatal exception. **Current:** passed in run `20260904T014648Z-1900fd6-736450`; the shell executed a command and reported Linux `7.2.3-blikvm-v4-serial`, followed by automated dmesg capture. **Fallback:** U-Boot prompt and known-good SD.

## M2 — MMC/SD storage

Enable MMC0/card detect only. **Pass:** the exact SD and its partitions appear reliably; the partition table and filesystem identities are readable; a known file on an existing ext4 partition is read through a `ro,noload` mount; the same result passes through archived `labctl` automation. **Current:** passed twice in runs `20260904T021821Z-969aa19-190597` and `20260904T021906Z-969aa19-622256`; `mmc0:59b4 EC1S5` and all three ext4 partitions matched vendor evidence, and p1 was mounted without journal replay to read `/etc/os-release`. No writes to the known-good card.

## M3 — Ethernet

Implement/validate H616 EMAC1 support and board RMII/PHY description. **Bring-up slice pass:** correct MAC and PHY enumerate, carrier reaches `LOWER_UP`, static `192.168.88.2/24` has no DHCP/DNS/default gateway, repeated pings reach `192.168.88.1`, and Ethernet dmesg has no persistent timeout/reset error while M1/M2 keep passing. **Current:** bring-up slice passed in consecutive runs `20260904T035100Z-792afb5-231884` and `20260904T035129Z-792afb5-102033`, including 10/10 pings total and Linux-confirmed PHY address 0/ID `0x00441400`. **Later qualification gate:** 1,000 pings without loss, sustained transfer, SSH, and testing across VPN changes; these broader items were intentionally out of scope for this isolated slice.

## M4 — USB host and capture

Enable host 1 and identify `345f:2131` by serial. **Host-only slice pass:** the
exact controller/PHY/VBUS path probes, a root hub appears, and the device
enumerates with stable identity/topology/speed and no persistent USB error
while M1-M3 keep passing. **Host baseline:** passed in three consecutive runs
`20260904T042809Z-04b3657-019979`, `20260904T042847Z-04b3657-561173`, and
`20260904T043155Z-04b3657-022990`; only EHCI1 is enabled and all MS2131 class
interfaces remain unbound. It is preserved by commit `b09f56d` and tag
`linux-7.2.3-usb-host-baseline`. **Raw UVC/V4L2 slice:** passed in runs
`20260904T062855Z-b09f56d-182887` and `20260904T063907Z-b09f56d-825527`;
interfaces 0/1 bind `uvcvideo`, `/dev/video0` captures, `/dev/video1` carries
metadata, all advertised modes are archived, and both boots captured 60
non-empty changing YUYV frames with clean USB/UVC dmesg. **Later integration
gate:** stable `/dev/kvmd-video`, `v4l2-compliance`, longer 1080p30 MJPEG and
signal loss/recovery qualification, then uStreamer smoke testing.

## M5 — USB gadget

Enable MUSB/configfs HID/MSD. **Pass:** keyboard; then both mouse modes; then an expendable read-only LUN; clean disconnect/rebind; full BliKVM reboot recovery on the controlled host.

**Current:** G1 keyboard-only qualification passed physical USB-PC reconnect,
host input press/release, and concurrent 60-frame changing UVC on two
consecutive RAM-only boots (`20260906T033008Z-9edcd3a-215238` and
`20260906T033114Z-9edcd3a-029399`). Preserved by annotated tag
`linux-7.2.3-hid-keyboard-baseline`. G2 absolute mouse and G3 relative mouse are also qualified at
`linux-7.2.3-hid-absolute-mouse-baseline` and
`linux-7.2.3-hid-relative-mouse-baseline`. G3 preserved all three HID functions
through physical reconnect, exact evdev tests and concurrent 60-frame UVC
on two consecutive RAM-only boots. G4 read-only storage is qualified; **M5 is complete** at
`linux-7.2.3-usb-gadget-baseline`. The final slice includes a focused MUSB
receive-queue correction and preserves all three HID functions unchanged.
Physical reconnect and consecutive full RAM boots
`20260906T065643Z-520a6eb-632211` / `20260906T065743Z-520a6eb-416769`
pass storage contents/hashes, rejected writes, software rebind, all HID input
tests and concurrent 60-frame changing UVC with zero startup/stream errors
and no unexpected USB reset. See [G4 evidence and rejected provisional
results](m5-storage-bringup.md) and [accepted HID evidence](m5-hid-bringup.md).


## M6 — GPIO/ATX

**Current: DEFERRED by explicit user decision. Not passed. Do not attempt during M7, M8-A or M8-B.**

Name/read status lines with libgpiod first. Use a meter/test fixture before outputs. **Pass:** inputs track known signals; power/reset pulses have verified polarity/duration; lines return inactive; no legacy sysfs GPIO dependency.

## M7 — Ubuntu 26.04.1 ARM64 rootfs

**Current: PASSED.** Reproducible Ubuntu Base 26.04.1 ARM64 RAM root, systemd/SSH, retained M5 hardware interfaces, and 20 consecutive clean software reboots. Annotated baseline: `ubuntu-26.04.1-rootfs-baseline`. See [M7 bring-up record](m7-ubuntu-rootfs-bringup.md).

Boot the pinned Ubuntu Base build. **Pass:** systemd reaches multi-user, network/SSH work, logs identify the artifact, clean reboot succeeds 20 times. Read-only policy is a later sub-gate.

## M7.5 — Pinned uStreamer and service-level video

**Current: PASSED.** Pinned uStreamer 6.65 plus a hashed device-FPS/native-quality
patch, Debian package `6.65-1blikvm2`, reproducible Ubuntu RAM image, serial and
capture-capability selected `/dev/kvmd-video`, and an unprivileged systemd
service. Two clean boots each passed 120 seconds of native MJPEG 1920x1080 at
30 device fps (29.7-29.8 delivered fps), three stop/start/restart iterations,
three automatic HDMI-loss recoveries, and all frozen M5 gadget regressions.
No uStreamer ERROR-level messages or unexpected USB/UVC errors occurred in the
accepted runs. Annotated baseline: `ubuntu-26.04.1-ustreamer-baseline`.
See [M7.5 qualification and rejected attempts](m75-ustreamer-bringup.md).
M6 remains deferred; this frozen standalone baseline is preserved.

## M8 — PiKVM

Package uStreamer, kvmd, web UI/nginx/auth, HID, MSD, and ATX in that order. **Pass:** authenticated browser video, keyboard/mouse, virtual read-only media, ATX state/pulse, service restart, and 24-hour soak with no memory/USB failures.

### M8-A — Minimal video-only kvmd

**Current: PASSED.** Pinned kvmd v4.213, reproducible ARM64 Debian package
`4.213-1blikvm1`, BliKVM platform, one kvmd-owned frozen uStreamer and Unix-only
API. Two full HIL boots pass lifecycle and three HDMI-loss recoveries each;
three further clean boots repeat API, 120-second 1080p30 and M5/M7 regressions.
All five deliver 29.7–29.8 fps with exact 30-fps device mode. Baseline:
`ubuntu-26.04.1-kvmd-video-baseline`. See [acceptance evidence](m8a-kvmd-video-bringup.md).
M8-A remains frozen with no web or hardware-control integration. M8 as a whole
remains incomplete; the separately qualified M8-B follows below.

### M8-B — Authenticated loopback Web UI

**Current: PASSED.** Pinned/reproducible `kvmd-web` 4.213-1blikvm2 and Ubuntu
web/auth dependencies, nginx HTTPS on target loopback only, upstream htpasswd
sessions and actual Chromium Web UI through SSH forwarding. Full preflight
qualifies auth/logout/WebSockets, moving video, clean nginx/kvmd restarts and
HDMI loss/restoration. Five subsequent consecutive clean boots restore the
stack automatically, each passing a 120-second >=27-fps HTTPS stream, exact
1080p30 capture mode and retained M5/M7 regressions. One video client is
qualified; the two-client diagnostic remains below the rate gate. Baseline:
`ubuntu-26.04.1-kvmd-web-baseline`. See [M8-B evidence](m8b-web-auth-bringup.md).
No LAN exposure or kvmd HID/MSD/ATX control is enabled. M6 remains deferred.

### M8-C — Controlled LAN HTTPS and client capacity

**Current: PASSED.** Direct HTTPS binds only `192.168.88.2:443`; nftables
allows only bridge source `192.168.88.1` on target eth0. Normal development-CA
browser trust and upstream kvmd authentication are mandatory. Direct browser,
API/WebSocket, lifecycle and HDMI recovery pass. Five consecutive clean boots
restore the same policy, exact 1080p30 mode and frozen M5/M7 regressions.
Two concurrent authenticated video clients each exceed the unchanged 27-fps
120-second gate in eight paired trials (29.785–29.919 fps).
Baseline: `ubuntu-26.04.1-kvmd-lan-baseline`.
See [M8-C evidence and capacity scope](m8c-lan-access-bringup.md).
No kvmd HID/MSD/ATX control is enabled; M6 remains deferred.

### M8-D — Authenticated keyboard and mouse

**Current: PASSED.** Pinned kvmd 4.213 controls the frozen keyboard, absolute
mouse and relative mouse through authenticated upstream API/WebSocket and the
actual Web UI. The sole M5 configfs owner is retained; deterministic function
identity grants only three nodes to unprivileged kvmd. Exact grabbed host
evdev events, repeated mode switching, logout/disconnect/restart cleanup,
fresh physical reconnect and five consecutive clean boots pass. Simultaneous
120-second video/HID workloads deliver 29.77–29.78 fps, including two clients.
Baseline: `ubuntu-26.04.1-kvmd-hid-baseline`.
See [M8-D report and evidence](m8d-kvmd-hid-bringup.md).
M6 GPIO/ATX remains **DEFERRED**; kvmd MSD control is not enabled.

### M8-E — Authenticated read-only MSD

**Current: PASSED.** Pinned kvmd 4.213 controls the approved immutable G4 image
through authenticated upstream API and actual Chromium UI. The sole configfs
owner remains `blikvm-gadget.service`; `mass_storage.g4/lun.0` and all frozen
USB/HID semantics are retained. A bounded helper delegates only attach/eject,
with the real namespace restricted to two writable LUN attributes. Upload,
remove, remote media and RW/CD-ROM modes remain unavailable.

Direct SCSI write protection, exact image/file hashes, daemon/session
lifecycles, fresh physical reconnect, concurrent storage/HID/two-client video,
and five consecutive clean boots pass. Video remains exact 1080p30, with
measured clients delivering 29.766–29.776 fps. Eject uses the explicitly
user-approved empty-LUN/MEDIUM NOT PRESENT policy; physical unplug removes
host objects. Baseline: `ubuntu-26.04.1-kvmd-msd-baseline`.
See [M8-E report](m8e-kvmd-msd-bringup.md) and [ownership record](m8e-msd-ownership.md).
M6 GPIO/ATX remains **DEFERRED**. Writable MSD, optional transports, VNC/IPMI
and final read-only-root remain excluded. A bounded integration soak and
image-production preparation slice is proposed only.

### M8-F — 24-hour core KVM soak

**Current: OPEN — Run 03 MEMORY REVIEW INCONCLUSIVE (outcome B).** Run 02
remains permanently **FAILED** at 14h54m on malformed JPEG markers. Candidate 2
completed its M8-E/reconnect prerequisites and Run 03 completed the full soak.
Independent review preserves all 27 passing automated gates, 2,583,555 frames
accepted by the unchanged strict parser, and a passing complete journal review.
Resource boundedness is not established: main kvmd grows through the first
generation's restart; the later observed plateau does not explain delayed
growth or attribute RAM-backed system-memory retention. FD/process/socket
counts are stable; a continuing leak is not demonstrated. Retain Run 03 as
completed functional evidence, not accepted M8-F. Propose a targeted memory
diagnostic; do not rerun the full soak yet. See the
[independent decision](evidence/m8f0/soak03/acceptance-review/README.md).
Preserve the frozen
M8-E core stack through one continuous 24-hour qualification with two
authenticated video clients, a real Web UI, moving HDMI, real host HID/MSD
checks, bounded lifecycle events and resource-growth review. See
[M8-F procedure and status](m8f-core-soak.md). M6 GPIO/ATX remains **DEFERRED**.
P1 standalone image assembly begins only after M8-F acceptance; physical
flashing remains a separate P2 qualification.

## M9 — Optional hardware

Add PCF8563 DTS, LCD, fan, buzzer, Wi-Fi/BT, and unused USB only after core KVM. **Pass:** individual HIL tests and no regression of M1-M8. LCD and wireless remain explicitly non-blocking.

## Recovery progression

Known-good SD is mandatory through M8. FEL can become a recovery milestone only after `version`, `sid`, SPL, and a full RAM-only U-Boot handoff are repeatable. Upstream U-Boot replacement is a separate project after Linux/PiKVM success, because the vendor bootloader already supplies the required TFTP loop.


### Candidate 2 physical reconnect and recovery review (2026-09-09)

Physical reconnect 03 passed on the recovered candidate boot. Independent VM
replay now passes the complete M8-E gate: five boots, 23 HID API runs, 615 browser
stages, 83 storage checks and 243 media transitions. The fresh recovery workload
also independently passes unchanged HID/video checks and 254 full-image direct
read-only storage reads. The target remained on the same boot across reconnect,
with identical USB descriptors and no kernel warning or unexpected target USB
reset in the final inventory.

The archive includes all three reconnect attempts. Attempt 01 timed out waiting
for disconnect. Attempt 02 recorded disconnect but the bridge reboot interrupted
it before a final result. The bridge boot time was 02:17 UTC; the shutdown cause
is unproven. UART recovery captured U-Boot and restored the exact candidate RAM
Image and accepted root/DTB. Recovery preflight 03 remains FAILED because an extra
host Shift autorepeat event violated the unchanged keyboard check. A separate,
unchanged repeat workload passed; this does not erase the first failure.

The reconnect/recovery archive SHA-256 is
`f53337a0c9d847afad3ec2e3238fd920b653dd26bbb671b977057f1ca16b9222`
(1,045,831 bytes, 1,480 files independently hash-verified). Raw evidence stays
private. Public replay and review are in
`research/evidence/m8f0/ms2131-candidate02/reconnect-vm-audit.json`.

This completes the candidate's prerequisite regression evidence, not M8-F
qualification. A NEW continuous 24-hour run must start from zero. Run 02 remains
permanently FAILED; diagnostics contribute zero time. P1 remains gated and
M6/ATX DEFERRED. No release/baseline tag is created.
