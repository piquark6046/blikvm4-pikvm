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

## M6 — GPIO/ATX

Name/read status lines with libgpiod first. Use a meter/test fixture before outputs. **Pass:** inputs track known signals; power/reset pulses have verified polarity/duration; lines return inactive; no legacy sysfs GPIO dependency.

## M7 — Ubuntu 26.04 rootfs

Boot the pinned Ubuntu Base build. **Pass:** systemd reaches multi-user, network/SSH work, logs identify the artifact, clean reboot succeeds 20 times. Read-only policy is a later sub-gate.

## M8 — PiKVM

Package uStreamer, kvmd, web UI/nginx/auth, HID, MSD, and ATX in that order. **Pass:** authenticated browser video, keyboard/mouse, virtual read-only media, ATX state/pulse, service restart, and 24-hour soak with no memory/USB failures.

## M9 — Optional hardware

Add PCF8563 DTS, LCD, fan, buzzer, Wi-Fi/BT, and unused USB only after core KVM. **Pass:** individual HIL tests and no regression of M1-M8. LCD and wireless remain explicitly non-blocking.

## Recovery progression

Known-good SD is mandatory through M8. FEL can become a recovery milestone only after `version`, `sid`, SPL, and a full RAM-only U-Boot handoff are repeatable. Upstream U-Boot replacement is a separate project after Linux/PiKVM success, because the vendor bootloader already supplies the required TFTP loop.
