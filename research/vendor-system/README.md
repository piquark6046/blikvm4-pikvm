# Vendor-system evidence

Captured 2026-09-03 from the installed BliKVM v4 over its built-in CH341-family UART at 115200 8N1. The installed root filesystem remained read-only. One controlled `reboot` was used to inspect U-Boot; no persistent U-Boot environment or target files were changed. Terminal ANSI control sequences were stripped from the text captures, but command output was otherwise retained.

Files:

- `system.txt`: kernel, command line, OS, block, USB, network, mounts, DT identity, and memory.
- `kernel.txt`: interrupts, I/O memory, registered devices, and full `dmesg` from the captured boot.
- `v4l2.txt`: V4L2 device discovery, formats, frame intervals, and controls.
- `boot-files.txt`: `/boot` file list, `armbianEnv.txt`, and `boot.cmd`.
- `vendor.dts`: direct `dtc -I dtb -O dts` decompilation of `/boot/dtb-5.19.4-sunxi64/allwinner/sun50i-h616-mangopi-mcore.dtb` (33 KiB DTB, 1,611-line DTS).
- `uboot.txt`: relevant raw excerpt from the controlled bootloader session.
- `host-current.txt`: current Fedora host USB, serial, network, firewall, and block-device inventory with the 5V/UART cable attached.
- `host-usb-pc.txt`: earlier host observation with the USB-PC cable attached.

Not collected: `lspci` is not meaningful on this target; `gpioinfo` was absent; `/proc/config.gz` was displayed but too large for the first console capture, so relevant configuration symbols were checked from `/boot/config-5.19.4-sunxi64` and are summarized in the research documents. The board revision printed on the PCB was not visually available.

The subsequent transport phase copied the exact kernel, uInitrd, and base DTB
from this read-only system. Their source paths, sizes, and hashes are recorded
in `artifacts/vendor/README.md`; the full TFTP boot evidence is in
`research/uart-uboot-tftp-phase.md`.
