# Research decision gate

Decision date: 2026-09-03. This gate authorizes only small, reversible bring-up work. It does not authorize replacing the known-good bootloader or assuming unverified carrier wiring.

## A. Is Linux 7.x on this board feasible?

**YES, WITH VENDOR PATCHES**

More precisely: use upstream Linux 7.x and write a small, reviewable equivalent of the required vendor functionality rather than importing the old vendor tree. UART, MMC, USB host/UDC, UVC, GPIO cdev, RTC, PMIC, thermal, watchdog, and RTL8723DS building blocks are upstream. The required board DTS is new work. Wired Ethernet is a real kernel gap because the carrier uses H616 EMAC1 at `0x05030000`, while v7.2 only defines/binds H616 EMAC0; EMAC1 needs a binding/driver/DTS addition and live validation.

## B. Is upstream-style USB gadget PiKVM functionality feasible?

**YES**

The live vendor Linux already uses the upstream MUSB/configfs/libcomposite interfaces to expose keyboard, two mouse profiles, and mass storage through USB-PC, and the Fedora host enumerated all functions. Linux 7.2 has the same controller/function drivers; the project kernel must explicitly enable configfs HID.

## C. Is the HDMI capture path usable with standard upstream Linux interfaces?

**YES**

The internal MacroSilicon `345f:2131` enumerates at USB2 high speed and binds to `uvcvideo`/`snd-usb-audio`. It provides MJPEG 1920x1080 at 30 fps and a range of MJPEG/YUYV modes. The port should use this UVC node directly, not Raspberry Pi CSI.

## D. Which final rootfs should be implemented first?

**Ubuntu 26.04 ARM64**

It matches current kvmd's Python 3.14 requirement and its systemd/udev/PAM/DBus service model, while official Ubuntu Base supplies a board-independent ARM64 filesystem. Alpine is recommended for the bring-up initramfs but would add a separate musl/OpenRC/systemd-assumption port to the final image.

## E. What should be the primary deploy/boot path?

**U-Boot + TFTP**

The existing bootloader's commands, Ethernet device, one-second interrupt, memory map, and load addresses were directly verified. Keep that bootloader on the known-good SD and load only new `Image`/DTB/initramfs artifacts into RAM. The physical Ethernet link is not yet cabled and is the next validation.

## F. What should be the recovery path?

**known-good SD**

FEL is electrically plausible through USB-PC but no `1f3a:efe8` device or full H616 handoff was tested, and current upstream still has active secure-handoff work. Preserve/image the current SD before future media changes.

## G. What is the first implementation task?

Implement `./lab/labctl detect`: a read-only, dependency-free host preflight that emits JSON; positively identifies the BliKVM CH341 UART, USB-PC composite gadget, or FEL device by USB identity; excludes the LattePanda serial device; inventories NIC carrier and required tools; and never opens or changes hardware.

Pass criteria:

1. Unit test with fake sysfs/devfs identifies all roles and stable serial paths.
2. Output is valid schema-versioned JSON with deterministic role names.
3. On this host with the 5V/UART cable attached, it finds exactly one `blikvm_uart` `1a86:7523` and does not label `3343:803a` as BliKVM.
4. Missing cable/tools are reported as readiness blockers, not crashes.
5. The command performs no writes outside normal process output.

Implementation result: **PASS**. `lab/labctl` and `tests/test_labctl.py` implement this slice. Three fixture tests pass. A privileged read-only live run found one `blikvm_uart` at `1a86:7523`, resolved `/dev/serial/by-id/usb-1a86_USB_Serial-if00-port0`, classified `3343:803a` as `host_lattepanda_mcu`, and reported the disconnected lab Ethernet link without crashing. No deploy, reboot, flash, FEL, or persistent target operation was added.
