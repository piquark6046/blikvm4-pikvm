# Bring-up milestones

Each milestone has an artifact, pass gate, and fallback. A later milestone may not paper over an earlier failure.

## M0 — Tooling and evidence

Build Linux/DT/initramfs in a pinned AMD64 container; implement device detection, UART capture/interrupt, source pinning, and run manifests. **Pass:** `labctl detect` identifies the CH341 UART; a dry build is reproducible; UART captures a complete known-good reboot. **Current:** detector and UART/evidence pass; builder, run manifests, and network remain.

## M1 — Linux 7.x console

Create the minimal board DTS and config. Boot `Image` + DTB + Alpine initramfs from vendor U-Boot. **Pass:** SPL/U-Boot load succeeds, `earlycon` and ttyS0 work, all four CPUs start, `/init` prints the run ID, no fatal exception. **Fallback:** U-Boot prompt and known-good SD.

## M2 — Storage

Enable MMC0/card detect. **Pass:** the exact SD appears, partition table is readable, 100 repeated reads show no I/O/CRC errors. No writes to the known-good card. Add expendable media before filesystem tests.

## M3 — Ethernet

Implement/validate H616 EMAC1 support and board RMII/PHY description. **Pass:** correct PHY ID, carrier, no dummy regulator, static `192.168.77.2`, 1,000 pings without loss, sustained transfer, and SSH. Test across VPN changes. This is the highest-risk kernel milestone.

## M4 — USB host and capture

Enable host 1 and identify `345f:2131` by serial. **Pass:** stable `/dev/kvmd-video`, V4L2 compliance, 300-frame 1080p30 MJPEG capture, signal loss/recovery, and uStreamer smoke test without USB reset.

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
