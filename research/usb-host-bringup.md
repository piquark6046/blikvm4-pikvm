# Linux 7.2.3 internal USB host bring-up

Status: passed on hardware in three consecutive RAM-only Linux 7.2.3 boots.
This slice stops at USB enumeration; UVC, V4L2/media, USB audio, HID, gadget,
UDC, and USB storage support remain disabled.

## Evidence and controller selection

The controller choice was made before changing the kernel config or board DT:

| Evidence | Observation | Conclusion |
|---|---|---|
| BliKVM v4 block diagram | MS2131 is wired to H616 USB1 | Select USB1, not USB0/2/3 |
| Captured vendor DT | EHCI/OHCI USB1 are `0x05200000`/`0x05200400`, both reference PHY index 1 | Use the upstream H616 USB1 nodes and PHY 1 |
| Vendor dmesg | `usb 2-1` enumerates `345f:2131` using `ehci-platform`; root serial is `5200000.usb` | The capture device is high-speed on EHCI1 root port 1 |
| Vendor `lsusb` / `lsusb -t` | `345f:2131 MACROSILICON USB2 Video`, direct port 1, 480 Mbit/s | No internal hub or other controller is involved |
| Vendor V4L2 topology | bus info is `usb-5200000.usb-1` | Independently confirms the controller and direct port |
| Captured vendor DT power node | fixed `usb1-vbus`, 5 V, active-high GPIO bank 2 pin 8 (PC8) | Model only this VBUS switch and attach it to USB PHY port 1 |

The vendor DT declares the PC8-controlled regulator but does not connect it to
the PHY's `usb1_vbus-supply`; the vendor image can therefore depend on firmware
state. The upstream board DT makes that consumer relationship explicit so the
PHY turns the rail on during host probe. The source rail feeding the switch is
not identified by the captured DT, so no `vin-supply` is guessed. Both vendor
and 7.2.3 logs report the PC pin bank's optional `vcc-pc` metadata as absent and
use a dummy regulator; this is not the 5 V VBUS rail, and PC8 drove the verified
VBUS switch correctly on every tested boot.

Only `&ehci1` and `&usbphy` are enabled. `&ohci1` remains disabled because the
MS2131 is a directly attached 480 Mbit/s device; OHCI is needed only for the
low/full-speed companion path. USB0 MUSB/UDC and USB2/USB3 remain disabled.

## Minimum software delta

The allnoconfig fragment adds USB core, new-device announcements, generic PHY,
the Allwinner USB PHY, and the generic platform EHCI driver. The resolved
config contains no OHCI HCD, MUSB, gadget/configfs, USB storage, media, V4L2,
or UVC driver. All USB support is built in because modules are still disabled.

Alpine BusyBox provides a flat `lsusb`, but its applet ignores `-t`. The
initramfs therefore installs one small sysfs-backed `lsusb` script rather than
libusb, usb.ids, and usbutils. It reports the numeric VID:PID, USB strings,
interface classes, bound driver, port path, and negotiated speed. This also
makes it explicit that all five MS2131 interfaces are present but unbound.

`labctl boot-usb` retains the serial-shell, read-only MMC/ext4, and isolated
Ethernet tests before checking, in order:

1. PHY driver binding;
2. the enabled 5 V VBUS regulator;
3. the one allowed EHCI controller;
4. the root hub;
5. MS2131 VID:PID and strings;
6. direct-port topology and 480 Mbit/s speed; and
7. absence of PHY, controller, reset, descriptor, and enumeration errors.

Each run archives `usb-dmesg.log`, `usb-controller-phy.log`,
`usb-enumeration-wait.log`, `lsusb.log`, `lsusb-tree.log`, full UART/dmesg,
exact artifacts and hashes, metadata, and `test-results.json`.

## Hardware validation

Run `20260904T042716Z-04b3657-434056` proved the controller, root hub, and
MS2131 enumeration, then exposed an automation-only race: the late USB device
announcement overwrote the first initramfs prompt. A bounded two-second probe
settle before eliciting a fresh prompt fixed this without changing the image.

Runs `20260904T042809Z-04b3657-019979`,
`20260904T042847Z-04b3657-561173`, and
`20260904T043155Z-04b3657-022990` all passed the complete boot and regression
sequence. The third used the final tightened validator requiring all five
interfaces to remain unbound at 480 Mbit/s:

- Linux reached the command-verified serial initramfs shell;
- MMC0 and all three existing ext4 partitions enumerated, p1 was read through
  `ro,noload`, and the block devices remained forced read-only;
- EMAC1 linked at 100/full, retained only `192.168.88.2/24` plus its connected
  route, and returned 15/15 total bounded pings to `192.168.88.1`;
- `5100400.phy` bound `sun4i-usb-phy`, with index 1 consumed by EHCI1;
- `usb1-vbus` was enabled at 5,000,000 microvolts with one consumer;
- the only bound USB controller was `5200000.usb` / `ehci-platform`;
- the single-port USB 2.0 root hub appeared, and `345f:2131` consistently
  enumerated as bus 1, device 2, sysfs `1-1`, serial `29404080`, at 480 Mbit/s;
- Video interfaces 0/1, Audio interfaces 2/3, and HID interface 4 all reported
  `Driver=[none]`, confirming no class support was enabled; and
- none of the three runs contained a USB PHY, VBUS, EHCI, descriptor, reset, timeout, or
  enumeration error.

The tested build artifacts are:

| Artifact | Size | SHA-256 |
|---|---:|---|
| `Image` | 5,892,104 | `59b39f786f1a78242871c7ea19c14b2f6e7ea079049d9daf665a49713f8a3e8e` |
| `sun50i-h616-blikvm-v4.dtb` | 20,552 | `4b94e64517a3eb117e9aa4d9287334a72ba8e82bf448d4d05d08a5ec1ed1f3ef` |
| `initramfs.cpio.gz` | 4,023,237 | `3d47eefa1ea5b781877ceca5e9a9ab975da9dea41f3dce9be1ef7f8c1ddf71da` |
| `linux.config` | 61,141 | `d30e24252433e212f18e61e7718257161c5f959b65807cc9aaa47f72da6c8703` |

Final build run `20260904T043401Z-04b3657-829112` reused
`out/build/linux-7.2.3` with three jobs, passed DT schema and artifact checks,
and reproduced these same four hashes without a clean operation.

All boots used immutable TFTP artifacts and session-only U-Boot changes. No
target storage, U-Boot environment, Ubuntu rootfs, PiKVM service, gadget, ATX,
or unrelated USB-controller change was made.
