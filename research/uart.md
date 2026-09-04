# UART console

Status: **working and suitable for automation**.

| Item | Verified value |
|---|---|
| Physical connector | BliKVM v4 `5V (UART)` USB-C connector |
| Bridge | QinHeng CH340/CH341 family, `1a86:7523`, USB revision 81.34 |
| Stable path | `/dev/serial/by-id/usb-1a86_USB_Serial-if00-port0` |
| Host topology fallback | `/dev/serial/by-path/pci-0000:00:14.0-usb-0:2:1.0-port0` |
| TTY at capture | `/dev/ttyUSB0` (do not hard-code) |
| Line settings | 115200 baud, 8 data bits, no parity, 1 stop bit, no flow control |
| Linux console | UART0, `serial@5000000`, `ttyS0` |
| U-Boot prompt | `=>` |
| Autoboot | `Autoboot in 1 seconds, press <Space> to stop` |
| Reliable interrupt | Open before reboot, continuously read, transmit a single ASCII space as soon as the countdown text appears, then wait for a line ending in `=>` |

The live capture showed both SPL/TF-A/U-Boot output and the Linux login prompt. Login input was accepted. The host's `/dev/ttyACM0` is a LattePanda Leonardo (`3343:803a`) and must never be mistaken for the target.

Direct access currently requires root because `/dev/ttyUSB0` is not accessible to the invoking account. A future host setup step should install a narrowly matched udev rule:

```udev
SUBSYSTEM=="tty", ATTRS{idVendor}=="1a86", ATTRS{idProduct}=="7523", SYMLINK+="blikvm-uart", GROUP="dialout", MODE="0660"
```

The VID:PID has no unique USB serial, so the rule deliberately does not claim that every CH341 is a BliKVM. If another `1a86:7523` is attached, topology or an explicit operator selection is required. Automation should use `termios`/pyserial directly, lock the device, timestamp raw bytes, tolerate ANSI output, and match bounded prompts rather than scrape an interactive terminal emulator.

Power warning: the 5V/UART port can also power the board. Follow the vendor's cable-order warning when 12 V is connected and prefer a data/power split arrangement for automated cycling.

