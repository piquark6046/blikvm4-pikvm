# BliKVM v4 Allwinner PiKVM port research

Research and direct hardware discovery were completed on 2026-09-03. The outcome is a viable port with one material Linux gap: this carrier uses H616's second Ethernet MAC, which is not described/bound in upstream Linux v7.2. The [decision gate](decision.md) selects upstream Linux 7.x plus a focused EMAC1 patch, an Alpine bring-up initramfs, Ubuntu 26.04 as the first final userspace, vendor U-Boot/TFTP for deployment, and known-good SD for recovery.

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

Core/clock/reset/pinctrl/UART/MMC/USB/UVC/configfs/GPIO/SPI/RTC/thermal/watchdog/RNG/AXP313A/RTL8723DS support exists in v7.2. There is no BliKVM/MCore DTS, configfs HID must be added to the config, and EMAC1 needs a kernel/binding addition. See [linux-7x-support.md](linux-7x-support.md).

## 7. Required DTS work

Build a clean board DTS from `sun50i-h616.dtsi`; use upstream OrangePi/BigTreeTech patterns and translate only verified live wiring. Stage UART+SD first, EMAC1 second, USB/UVC/UDC and named GPIOs third; defer LCD/wireless/optional hardware. See [device-tree-plan.md](device-tree-plan.md).

## 8. Video capture

The internal device is standard USB2 UVC, not CSI. Use serial `29404080` to create `/dev/kvmd-video`; start with 1080p30 MJPEG pass-through and exercise signal loss. See [video-capture.md](video-capture.md).

## 9. USB gadget

USB-PC/MUSB/configfs already works end to end as keyboard, two mouse modes, and mass storage. Recreate it with upstream configfs, stable udev links, and safe LUN handling. FEL and gadget share USB0. See [usb-gadget.md](usb-gadget.md).

## 10. PiKVM portability

Current kvmd uses libgpiod v2 and portable Linux interfaces, but its packaging/services are Arch/systemd-centric. A Bli platform config, udev rules, Debian package dependency map, and removal of Raspberry Pi assumptions are required. See [pikvm-port.md](pikvm-port.md).

## 11. Ubuntu feasibility

Ubuntu Base 26.04.1 ARM64 is the recommended first final rootfs. It supplies Python 3.14 and the systemd/PAM/DBus environment current kvmd expects. Builds must be pinned, checksummed, key-only, and eventually split read-only OS from persistent data. See [ubuntu-rootfs.md](ubuntu-rootfs.md).

## 12. Alpine feasibility

Alpine 3.24.1 is recommended for the bring-up initramfs. It is only “MAYBE” for final PiKVM because uStreamer works on musl but kvmd's full service/dependency stack would require a maintained OpenRC port. See [alpine-rootfs.md](alpine-rootfs.md).

## 13. Development network

Reserve `enp1s0` as `192.168.77.1/24` and target `192.168.77.2/24`, with no gateway and `never-default`. Internet stays on `wlo1`, Proton on `wg_profile`, and TFTP binds only to the lab NIC. A physical Ethernet link is currently absent. See [lab-network.md](lab-network.md).

## 14. Boot loop

Keep vendor U-Boot and load immutable per-run kernel/DTB/initramfs paths over TFTP into verified addresses. Capture UART from before reboot through userspace tests and never call `saveenv`. Exact commands are in [boot-loop.md](boot-loop.md).

## 15. Automation architecture

`labctl` should provide JSON-first detection, build, UART, boot, test, cycle, FEL, collection, and later explicit power control. Runs are immutable, stage-classified, hashed, locked, and credential-redacted. See [automation-design.md](automation-design.md).

## 16. Major risks

1. EMAC1 is not upstream-complete and blocks the preferred TFTP/SSH loop.
2. PMIC naming/old firmware inconsistency requires conservative rail validation.
3. FEL reachability and secure SPL handoff are unproven.
4. Exact carrier/PHY revision is unknown.
5. PiKVM packaging has many optional/native dependencies; minimize features first.
6. One-second U-Boot interruption needs a robust state machine.

## 17. First implementation milestone

The small read-only `labctl detect` slice defined in [decision.md](decision.md) is implemented and fixture-tested. Live verification found exactly one `1a86:7523` BliKVM UART, selected its `/dev/serial/by-id` path, excluded the `3343:803a` LattePanda MCU, protected the known host boot media identity, and correctly reported the absent Ethernet carrier as a blocker. The next M0 slice is the pinned Linux 7.x/DT/initramfs builder. Do not implement flashing or replace U-Boot. Full milestone gates are in [milestones.md](milestones.md).

All external references, classifications, access dates, and pinned commits are in [sources.md](sources.md). Raw live evidence is under [vendor-system](vendor-system/README.md).
