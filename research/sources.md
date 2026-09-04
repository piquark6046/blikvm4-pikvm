# Sources

Access date for every external source: **2026-09-03**. Live-board evidence is preserved under [vendor-system](vendor-system/README.md) and takes priority over web documentation.

| ID | Title / URL | Claim supported | Classification |
|---|---|---|---|
| S01 | [BliKVM v4 Allwinner guide](https://www.blikvm.com/docs/device-guides/BliKVM-v4-guide/) | 5V-port CH341 UART `1a86:7523`, 115200 console, cable power warning, 4K30 input and default 1080p behavior | Official vendor |
| S02 | [BliKVM v4 datasheet](https://www.blikvm.com/docs/device-guides/BliKVM-v4-datasheet/) | H616/H313 product family, 1 GiB, ports, 100M/PoE, display, Wi-Fi/BT, MJPEG | Official vendor |
| S03 | [BliKVM v4 development resources](https://www.blikvm.com/docs/development/dev-BliKVM-v4-Allwinner/) | Buttons, LEDs, ATX, fan, buzzer, ST7789/SPI GPIO assignments and active levels | Official vendor |
| S04 | [BliKVM product comparison](https://www.blikvm.com/docs/) | MS2131-family capture, HDMI loop-through, 100M Ethernet, RTC/display and model comparison; also documents a conflicting H.264 statement | Official vendor |
| S05 | [BliKVM v4 block diagram](https://www.blikvm.com/assets/images/hardware-24813e4c73483a56a888cb8eadb3bd96.png) | USB0 USB-PC, USB1 MS2131, USB2 external, UART0 bridge, RTL8723DS SDIO, PCF8563 at 0x51, SPI1 LCD, ATX GPIO | Official vendor image |
| S06 | [BliKVM downloads](https://blikvm.com/download/) | Vendor v4 image is a 64-bit read-only Armbian image and historically used an old kernel | Official vendor |
| S07 | [BliKVM OS flashing](https://blikvm.com/docs/getting-started/flashing-os/) | Allwinner-specific image, SD requirements, and reflashing recovery | Official vendor |
| S08 | [BliKVM video modes](https://www.blikvm.com/docs/video/video-modes/) | v4 USB video/MJPEG path; used to frame the documentation conflict around H.264 | Official vendor |
| S09 | [BliKVM authentication](https://blikvm.com/docs/getting-started/auth/) | Vendor-documented console account used for the read-only baseline login | Official vendor |
| S10 | [MangoPi MCore H616](https://mangopi.org/mcoreh616) | H616/H313 module options, 1 GiB/512 MiB DDR3L, AXP313A, USB/EMAC/storage capabilities | Official module vendor |
| S11 | [BliKVM software v2.2.3-alpha at `3e34c04`](https://github.com/blikvm/blikvm/tree/3e34c04a1dfa84636050585d12d5e585098258ea) | Runtime board detection, GPIO mappings, fan/RTC logic, old configfs gadget, capture-device selection | Vendor source |
| S12 | [Linux kernel releases](https://www.kernel.org/) | v7.2.3 was current stable and v7.3-rc1 mainline on the research date | Upstream |
| S13 | [Linux v7.2 source](https://github.com/torvalds/linux/tree/v7.2) | H616 DTSI, drivers, bindings, defconfig and absence of a BliKVM/MCore board DTS; inspected commit `8d3ae59288f1e7d58d76558a6ee96d533bc5019f` | Upstream |
| S14 | [Linux v7.2 Allwinner DTS directory](https://github.com/torvalds/linux/tree/v7.2/arch/arm64/boot/dts/allwinner) | Closest board DTS choices and explicit absence of BliKVM/MCore | Upstream |
| S15 | [U-Boot v2026.07 source](https://github.com/u-boot/u-boot/tree/v2026.07) | H616 SPL/DDR support and defconfigs; no MangoPi MCore/BliKVM definition; inspected commit `ece349ade2973e220f524ce59e59711cc919263f` | Upstream |
| S16 | [U-Boot Allwinner board documentation](https://docs.u-boot.org/en/latest/board/allwinner/sunxi.html) | Integrated SPL image, H616 TF-A requirement, 8/128 KiB boot locations, FEL VID:PID and BootROM fallback behavior | Upstream documentation |
| S17 | [sunxi-tools at `d7bbd172`](https://github.com/linux-sunxi/sunxi-tools/tree/d7bbd172a5da601a08f94479de308c6fb714a19a) | Current H616 `0x1823` recognition, FEL/SID/SPI implementation | Upstream linux-sunxi source |
| S18 | [H616 secure-FEL handoff PR #236](https://github.com/linux-sunxi/sunxi-tools/pull/236) | Secure-FEL SPL handoff remains active upstream work | Upstream proposed change |
| S19 | [H616/MangoPi FEL timeout issue #182](https://github.com/linux-sunxi/sunxi-tools/issues/182) | Direct community evidence that FEL version/SPL can work on MCore while full U-Boot handoff timed out | Community issue/evidence |
| S20 | [H616-mangopi at `3d607f3`](https://github.com/mamin27/H616-mangopi/tree/3d607f347c21ef0dfa7cbd3cdd352d41af473700) | Additional MCore DTS lead; treated as a vendor-style/decompiled reference, not upstream truth | Community |
| S21 | [Bli-PiKVM](https://github.com/RainCat1998/Bli-PiKVM) | Prior non-Raspberry-Pi kvmd attempt and vendor GPIO ownership conflicts; old/broadly privileged approach not reused | Community |
| S22 | [kvmd v4.213 at `387846d`](https://github.com/pikvm/kvmd/tree/387846d22fa807f97de09750c32c1c9b26d36c1c) | Current Python/package dependencies, libgpiod v2 plugins, systemd/udev/configfs/nginx paths | PiKVM upstream |
| S23 | [uStreamer at `3af6bfa`](https://github.com/pikvm/ustreamer/tree/3af6bfac0f11dddd7e743e914705a6b0c58eb9e4) | V4L2/MJPEG architecture; Ubuntu/Debian and Alpine build dependencies; Alpine `WITH_PTHREAD_NP=0` | PiKVM upstream |
| S24 | [PiKVM FAQ](https://github.com/pikvm/pikvm/blob/master/docs/faq.md) | Non-Raspberry-Pi ports require a custom OS/config/udev setup; PiKVM OS is Arch Linux ARM | PiKVM upstream documentation |
| S25 | [PiKVM OS source](https://github.com/pikvm/os) | Official image build is Arch Linux ARM and carries PiKVM-specific packaging/image policy | PiKVM upstream |
| S26 | [Ubuntu Base 26.04.1 release](https://cdimage.ubuntu.com/ubuntu-base/releases/26.04/release/) | Official board-independent ARM64 rootfs artifact | Official Ubuntu/Canonical |
| S27 | [Ubuntu Base SHA256SUMS](https://cdimage.ubuntu.com/ubuntu-base/releases/26.04/release/SHA256SUMS) | Published hash for the pinned 26.04.1 ARM64 archive | Official Ubuntu/Canonical |
| S28 | [Ubuntu 26.04 Python 3.14 package](https://packages.ubuntu.com/resolute/python3.14) | ARM64 Python 3.14 package aligns with current kvmd ABI requirement | Official Ubuntu package index |
| S29 | [Alpine 3.24.1 ARM64 release directory](https://dl-cdn.alpinelinux.org/alpine/latest-stable/releases/aarch64/) | Official minirootfs, signatures, checksums, and ARM64 release version | Official Alpine |
| S30 | [Alpine initramfs/mkinitfs](https://wiki.alpinelinux.org/wiki/Initramfs_init) | `mkinitfs` staged-root/module workflow and purpose | Alpine documentation |

## Source snapshots

Temporary shallow clones were inspected without adding them as submodules:

```text
blikvm       3e34c04a1dfa84636050585d12d5e585098258ea  v2.2.3-alpha
linux        8d3ae59288f1e7d58d76558a6ee96d533bc5019f  v7.2
u-boot       ece349ade2973e220f524ce59e59711cc919263f  v2026.07
sunxi-tools  d7bbd172a5da601a08f94479de308c6fb714a19a
H616-mangopi 3d607f347c21ef0dfa7cbd3cdd352d41af473700
kvmd         387846d22fa807f97de09750c32c1c9b26d36c1c  v4.213
ustreamer    3af6bfac0f11dddd7e743e914705a6b0c58eb9e4
```

