# BliKVM v4 Allwinner PiKVM port research

Research and direct hardware discovery were completed on 2026-09-03. The UART/U-Boot/TFTP transport phase is also complete; see the [live phase evidence](uart-uboot-tftp-phase.md). The viable port now has passing Linux 7.2.3 serial, MMC/read-only ext4, H616 EMAC1 Ethernet, internal USB host, and raw UVC/V4L2 capture slices. The [decision gate](decision.md) selects upstream Linux 7.x plus a focused EMAC1 patch, an Alpine bring-up initramfs, Ubuntu 26.04 as the first final userspace, vendor U-Boot/TFTP for deployment, and known-good SD for recovery.

## 1. Confirmed hardware

The connected unit is an Allwinner H616 (`0x1823`) MangoPi MCore with 1 GiB RAM and a 59.7 GiB removable SD. Direct probes confirmed UART0, SD/MMC0, H616 EMAC1/RMII, RTL8723DS, MUSB UDC, three USB host pairs, MacroSilicon `345f:2131` UVC/audio capture, PCF8563 RTC, and the live configfs HID/MSD gadget. See [hardware.md](hardware.md).

## 2. Uncertain hardware

The exact BliKVM carrier revision, Ethernet PHY part marking/reset wiring, DRAM package/type marking (DDR3L is vendor-supported/probable), SPI-NOR population, and exact external USB routing were not visually verified. The PMIC is AXP313A-class/ID `0x4b`, but old firmware uses inconsistent AXP1530/AXP305 names. These are explicit validation items, not assumptions.

## 3. Boot chain

H616 BootROM -> U-Boot SPL 2021.10-armbian -> TF-A BL31 v2.8 -> U-Boot 2021.10-armbian -> SD `/boot/boot.scr` -> `Image`/legacy `uInitrd`/MCore DTB -> Linux 5.19.4 -> Armbian Jammy systemd. The root is ext4/read-only on partition 1; partition 3 is writable at `/mnt`. See [boot-chain.md](boot-chain.md).

## 4. UART method

Use the 5V/UART USB-C port, 115200 8N1, stable path `/dev/serial/by-id/usb-1a86_USB_Serial-if00-port0`. U-Boot gives one second and accepts space to stop at `=>`. The LattePanda `/dev/ttyACM0` is unrelated. See [uart.md](uart.md).

## 5. FEL feasibility

**POSSIBLE BUT INCONVENIENT.** USB-PC is on USB0 and likely carries FEL, but the board was not put into FEL and current sunxi-tools still has H616 secure-handoff work in flight. See [fel.md](fel.md).

## 6. Linux 7.x status

Core/clock/reset/pinctrl/UART/MMC/USB/UVC/configfs/GPIO/SPI/RTC/thermal/watchdog/RNG/AXP313A/RTL8723DS support exists in v7.2. There is no upstream BliKVM/MCore DTS, configfs HID must later be added to the config, and the required focused EMAC1 kernel/binding addition is now validated. See [linux-7x-support.md](linux-7x-support.md) and [ethernet-bringup.md](ethernet-bringup.md).

## 7. Required DTS work

Build a clean board DTS from `sun50i-h616.dtsi`; use upstream OrangePi/BigTreeTech patterns and translate only verified live wiring. Stage UART+SD first, EMAC1 second, USB/UVC/UDC and named GPIOs third; defer LCD/wireless/optional hardware. See [device-tree-plan.md](device-tree-plan.md).

## 8. Video capture

The internal device is standard USB2 UVC, not CSI. Linux 7.2.3 now binds its
video interfaces to upstream `uvcvideo`, enumerates the complete MJPEG/YUYV
mode table, and captures non-empty changing frames across two full RAM-only
boots. Use serial `29404080` for the eventual `/dev/kvmd-video` link; uStreamer
and PiKVM video integration are now qualified in the userspace slices below. See [video-capture.md](video-capture.md)
and [uvc-v4l2-bringup.md](uvc-v4l2-bringup.md).

## 9. USB gadget

USB-PC/MUSB/configfs already works end to end as keyboard, two mouse modes, and mass storage. Recreate it with upstream configfs, stable udev links, and safe LUN handling. FEL and gadget share USB0. See [usb-gadget.md](usb-gadget.md).

## 10. PiKVM portability

Current kvmd uses libgpiod v2 and portable Linux interfaces, but its packaging/services are Arch/systemd-centric. A Bli platform config, udev rules, Debian package dependency map, and removal of Raspberry Pi assumptions are required. See [pikvm-port.md](pikvm-port.md).

## 11. Ubuntu feasibility

Ubuntu Base 26.04.1 ARM64 is the recommended first final rootfs. It supplies Python 3.14 and the systemd/PAM/DBus environment current kvmd expects. Builds must be pinned, checksummed, key-only, and eventually split read-only OS from persistent data. See [ubuntu-rootfs.md](ubuntu-rootfs.md).

## 12. Alpine feasibility

Alpine 3.24.1 is recommended for the bring-up initramfs. It is only “MAYBE” for final PiKVM because uStreamer works on musl but kvmd's full service/dependency stack would require a maintained OpenRC port. See [alpine-rootfs.md](alpine-rootfs.md).

## 13. Development network

`enp1s0` is configured as `192.168.88.1/24` and the target uses `192.168.88.2/24`, with no gateway/DNS and `never-default`. Internet remains on `wlo1`, Proton on `wg_profile`, and TFTP binds only to the lab NIC. The link is live at 100 Mb/s full duplex. See [lab-network.md](lab-network.md).

## 14. Boot loop

Keep vendor U-Boot and load immutable per-run kernel/DTB/initramfs paths over TFTP into verified addresses. Capture UART from before reboot through userspace tests and never call `saveenv`. Exact commands are in [boot-loop.md](boot-loop.md).

## 15. Automation architecture

`labctl` should provide JSON-first detection, build, UART, boot, test, cycle, FEL, collection, and later explicit power control. Runs are immutable, stage-classified, hashed, locked, and credential-redacted. See [automation-design.md](automation-design.md).

## 16. Major risks

1. EMAC1 is not upstream-complete for Linux 7.x, so the validated focused patch remains a maintenance item; the vendor U-Boot TFTP loop is proven with a guarded RAM-only correction for its bad PHY address.
2. PMIC naming/old firmware inconsistency requires conservative rail validation.
3. FEL reachability and secure SPL handoff are unproven.
4. Exact carrier/PHY revision is unknown.
5. PiKVM packaging has many optional/native dependencies; minimize features first.
6. One-second U-Boot interruption needs a robust state machine.

## 17. First implementation milestone

`labctl` now builds, publishes, boots, captures, and classifies the minimal Linux 7.2.3 slice. The reproducible builder, eleven tests, minimal DTS/binding, Alpine initramfs, and command-verified real-hardware serial shell pass are recorded in [linux-7x-bringup.md](linux-7x-bringup.md). Passing run `20260904T014648Z-1900fd6-736450` also captured dmesg automatically. No flashing or U-Boot replacement was used. Full milestone gates are in [milestones.md](milestones.md).

All external references, classifications, access dates, and pinned commits are in [sources.md](sources.md). Raw live evidence is under [vendor-system](vendor-system/README.md).

## 18. MMC/SD slice

The accepted serial baseline is preserved as commit `969aa19` and tag
`linux-7.2.3-serial-baseline`. The next isolated slice enables only MMC0,
block/MS-DOS partition parsing, the existing ext4 format, and the vendor's
always-on 3.3 V SD/PF supply. Its evidence derivation and read-only automated
test are in [mmc-sd-bringup.md](mmc-sd-bringup.md).

## 19. Ethernet slice

The H616 EMAC1/RMII slice passed two consecutive RAM-only Linux 7.2.3 boots.
Linux independently found the Clause-22 PHY at address 0 with ID `0x00441400`,
`eth0` reached 100/full `LOWER_UP`, and 10/10 bounded pings reached the isolated
LattePanda address with no DHCP, DNS, default route, or storage write. The
upstream/vendor comparison, minimal patch, failure isolation, and archived run
IDs are in [ethernet-bringup.md](ethernet-bringup.md).

## 20. Internal USB host slice

Only H616 USB1 EHCI, PHY index 1, and the PC8-controlled `usb1-vbus` rail are
enabled. Two consecutive full RAM boots enumerated the internal MS2131 as
`345f:2131` directly on root port 1 at 480 Mbit/s while preserving MMC and
Ethernet. All Video/Audio/HID interfaces remain unbound because media, UVC,
audio, HID, gadget, and UDC support are intentionally outside this slice. See
[usb-host-bringup.md](usb-host-bringup.md).

## 21. Raw UVC/V4L2 slice

The USB-host baseline is preserved as commit `b09f56d` and tag
`linux-7.2.3-usb-host-baseline`. The next isolated image enables only the media,
V4L2/videobuf2, USB media, and upstream UVC core needed by MS2131. Two complete
RAM-only boots bound interfaces 0/1, created one capture and one metadata node,
enumerated 22 format-size records and 84 intervals, and each captured 60
non-empty YUYV frames with 60 unique hashes and no persistent USB/UVC errors.
The deterministic source, mode matrix, automation, and evidence are in
[uvc-v4l2-bringup.md](uvc-v4l2-bringup.md).


## 22. M5 HID baselines

G1 keyboard, G2 absolute mouse and G3 relative mouse are qualified. G3 retains
all three functions with exact report descriptors, configfs-derived device
mapping, grabbed host evdev tests, software/physical reconnect, concurrent
60-frame changing MS2131 capture and two consecutive RAM-only boots. The
annotated tag is `linux-7.2.3-hid-relative-mouse-baseline`. Read-only disposable
mass storage is qualified as G4 with the focused MUSB receive-queue fix,
physical reconnect and two consecutive full RAM boots. All retained HID,
storage protection and concurrent zero-error UVC checks pass; M5 is complete. See [G4 status](m5-storage-bringup.md) and
[the accepted HID qualification](m5-hid-bringup.md).


## 23. Ubuntu and uStreamer userspace baselines

M7 Ubuntu 26.04.1 ARM64 is frozen at `ubuntu-26.04.1-rootfs-baseline`.
The next isolated [M7.5 uStreamer slice](m75-ustreamer-bringup.md) is qualified:
pinned Debian package, stable MS2131 capture identity, unprivileged systemd
service, real native 1080p30 MJPEG, automatic HDMI recovery and retained M5
functionality across two clean RAM boots. Its baseline tag is
`ubuntu-26.04.1-ustreamer-baseline`. M6 remains deferred; the standalone M7.5 baseline remains frozen.

## 24. M8-A video-only kvmd

[M8-A is qualified](m8a-kvmd-video-bringup.md) at
`ubuntu-26.04.1-kvmd-video-baseline`: pinned/reproducible ARM64 package, BliKVM
configuration, one owner of the frozen uStreamer, local Unix API, moving
1080p30 video, HDMI recovery and five clean boots with retained M5/M7 gates.
This frozen M8-A slice has no web or hardware-control integration. The separate
M8-B qualification follows below; M6 remains deferred.

## 25. M8-B authenticated loopback web delivery

[M8-B is qualified](m8b-web-auth-bringup.md) at
`ubuntu-26.04.1-kvmd-web-baseline`: pinned web/auth packages, loopback-only nginx
HTTPS, upstream htpasswd sessions, real PiKVM Web UI through SSH forwarding,
exact frozen video ownership/mode, HDMI and service recovery, and five clean
boots with 120-second HTTPS video and retained gadget regressions. LAN exposure
and kvmd HID/MSD/ATX control remain excluded; M6 remains deferred. Controlled
LAN qualification is recorded separately as M8-C below.


## 26. M8-C controlled LAN HTTPS

[M8-C bring-up](m8c-lan-access-bringup.md) qualifies restricted direct HTTPS,
normal development-CA trust, upstream authentication, two-client 1080p30
capacity, lifecycle recovery and five clean boots. Hardware-control integration
was qualified separately in M8-D below.


## 27. M8-D authenticated HID

[M8-D bring-up](m8d-kvmd-hid-bringup.md) qualifies upstream keyboard and both
mouse modes through trusted HTTPS, the real Web UI and grabbed host evdev.
It retains the sole frozen gadget owner, narrow permissions, exact descriptors,
read-only MSD regression and two-client 1080p30 video. Cleanup, reconnect and
five clean boots pass. M8-E read-only MSD integration follows below;
M6 GPIO/ATX remains deferred.


## 28. M8-E authenticated read-only MSD

[M8-E bring-up](m8e-kvmd-msd-bringup.md) qualifies approved read-only media
selection, attach and eject through upstream API and real Chromium UI.
The [ownership record](m8e-msd-ownership.md) preserves the sole frozen gadget
owner and documents narrow privilege delegation and approved eject semantics.
SCSI write protection, immutable hashes, physical reconnect, concurrent
HID/storage/two-client 1080p30 video and five clean boots pass. Writable media,
M6 GPIO/ATX and later integrations remain excluded.

## M8-F2 bounded logging

[M8-F2](m8f2-bounded-logging.md) explains the M8-F1 log growth and demonstrates automatic bounded journal retention with passing two-hour browser/video/HID/MSD evidence. At that supplemental checkpoint M8-F remained open; the later Run 04 acceptance below supersedes that gate.

## M8-F core acceptance and P1 image production

**CORE KVM SOAK PASSED; ATX DEFERRED.** Run 04 is accepted at
`ubuntu-26.04.1-kvmd-core-soak-baseline`, commit `4cf664a`, for production
candidate `8650c66`. [Run 04 evidence](evidence/m8f/run04/README.md) unlocks P1.

[P1 image production](p1-image-production.md) passes frozen-input, vendor raw
layout, independent byte-identical A/B image, read-only offline filesystem/boot,
credential scan and private enrollment gates. Public artifacts are under
`out/images/`; the [design](image-production-design.md) keeps vendor SPL/TF-A/
U-Boot and one read-write ext4 SD root. No physical SD was written. P2 standalone
hardware boot remains untested; its guarded flash/readback/regression procedure
is proposed only. M6/ATX, full M8 and final RO/overlay remain deferred/unaccepted.


## P2 attempt 01 and P2-R1

[P2 attempt 01](p2-standalone-sd-bringup.md) is permanently **FAILED**: Ethernet
and trusted HTTPS recovered after a cold offline boot, but SSH refused connections.
The failure checkpoint is pushed as `b19036e`; the untouched recovery SD was
restored by the operator. P1 remains historically offline-passed.
[P2-R1 Candidate 1](p2-r1-offline-ssh-recovery.md) passes fresh reproducible offline
assembly/enrollment with only ConfigureWithoutCarrier=yes added to standalone
network configuration. Narrow HIL and fresh P2 attempt 02 remain NOT STARTED.
The preceding P1 no-write/not-tested wording records the state at P1 acceptance.
Run 04 remains the accepted core soak; M6/ATX and RO/overlay remain deferred.


P2-R1 update (2026-09-13): [Candidate 1 narrow HIL passed and the revised image is
frozen](p2-r1-offline-ssh-recovery.md#candidate-1-decision-and-freeze--2026-09-13).
SSH binds the approved address before carrier with zero restarts; cold offline
recovery and the separate carrier cycle pass. Candidate 2 is unnecessary.
Fresh P2 attempt 02 remains NOT STARTED; diagnostic evidence earns no credit.

P2 final update (2026-09-13): [fresh attempt 02 PASSED](p2-standalone-sd-bringup.md#final-acceptance--p2-attempt-02-passed-2026-09-13)
using frozen P2-R1 Candidate 1. Both offline-Ethernet cold boots recovered trusted
HTTPS and enrolled SSH automatically with zero SSH restarts. Complete core,
physical USB reconnect, persistence, normal reboot and retained-artifact gates
passed. Acceptance includes the explicitly approved early cold-boot UART gap;
the normal reboot captured the full firmware chain. Earlier NOT STARTED/pending
entries are historical checkpoints. Attempt 01 remains FAILED; P1 original
remains historically offline-passed. M8-F Run 04 remains the accepted core soak.
P3 has not begun; M6/ATX and RO/overlay remain DEFERRED. No baseline tag is created.


P3 update (2026-09-13): the annotated `standalone-sd-core-kvm-baseline` tag is
verified on origin at accepted P2 commit `1fa1a7c`. [P3-A attempt 01](p3-standalone-stability.md)
stopped FAILED during cycle 1 browser smoke because a bridge acknowledgment
file was unreadable by Chromium. The reboot/startup checks passed, but no P3
cycle earns acceptance credit. The private failure archive is independently
verified. No power-loss or second-card test ran; P3 remains NOT ACCEPTED.
M6/ATX, writable MSD and RO/overlay remain DEFERRED.

P3-A attempt-02 preparation update (2026-09-13): the separate bridge correction
passed initial permission checks and one functional Chromium smoke, but a later
check found previous browser evidence directories still writable by the browser
account. The second preflight was stopped. Both archives are independently
verified; the [failed preflight checkpoint](p3-standalone-stability.md) consumes
zero reboot cycles. Attempt-02 reboot sequence has NOT STARTED. All 10,690
target hashes and retained protected evidence remain unchanged. P2 stays PASSED;
P3 remains NOT ACCEPTED; P3-B/P3-C have not started. No new tag was created.


P3-H2 update (2026-09-13): [evidence-directory isolation FAILED before the first
browser launch](p3-standalone-stability.md#p3-h2--evidence-isolation-stopped-failed-2026-09-13).
The actual browser UID created a zero-byte probe in an inherited root-owned
0777 attempt-01 output omitted from the sealing migration. The probe and changed
directory timestamps are preserved; existing protected file contents and prior
archives are unchanged. The 78-file private archive independently replays as
FAILED_CONFIRMED. Both target inventories match all 10,690 hashes and the same
boot/identity/service generations. No browser smoke or reboot ran; no later
preflight or P3-A/B/C work started. P2 remains PASSED; P3 remains UNACCEPTED.
M6/ATX, writable MSD and RO/overlay remain DEFERRED. No tag was created.
