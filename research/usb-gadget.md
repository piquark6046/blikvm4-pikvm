# USB gadget requirements

Status: **the upstream-style PiKVM gadget path is directly proven on the current hardware**.

The USB-PC connector is wired to H616 USB0 MUSB at `0x05100000`. Linux exposes UDC `musb-hdrc.2.auto`; the live DT uses `dr_mode = "peripheral"`. The vendor system configures one configfs composite gadget with:

- `hid.keyboard` -> `/dev/hidg0`;
- `hid.mouse0` -> `/dev/hidg1`;
- `hid.mouse1` -> `/dev/hidg2`;
- `mass_storage.0`;
- UDC bound through `/sys/kernel/config/usb_gadget/g1/UDC`.

When attached to the Fedora host it enumerated at high speed as `1d6b:0106`, product `Multifunction`, manufacturer `BliKVM`, with a boot keyboard, two mouse-class HID interfaces, and SCSI bulk-only mass storage. This end-to-end observation proves controller, PHY, connector, configfs HID, and mass-storage behavior on the vendor kernel. The older vendor source creates keyboard plus absolute mouse and optionally MSD; the newer live image adds a second mouse profile, which is desirable for PiKVM absolute/relative modes.

## Kernel/userspace requirements

Enable `CONFIG_USB_MUSB_SUNXI`, `CONFIG_USB_GADGET`, `CONFIG_USB_LIBCOMPOSITE`, `CONFIG_USB_CONFIGFS`, `CONFIG_USB_CONFIGFS_F_HID`, and `CONFIG_USB_CONFIGFS_MASS_STORAGE`. Stock v7.2 `arm64_defconfig` does not select configfs HID, so the project config must. Use PiKVM's `kvmd-otg`/configfs model after adapting paths and udev permissions; never assume `/dev/hidgN` ordering without verifying function `dev` attributes.

The MUSB PHY/extcon supplies VBUS state. No USB mux or carrier GPIO was found in the live DT/source. USB gadget and FEL share USB0/USB-PC and therefore cannot operate simultaneously. BootROM owns it in FEL; Linux owns it after MUSB probes.

## Minimal hardware test sequence

1. Bind keyboard only; verify enumeration and a controlled key event.
2. Unbind, add absolute and relative mouse functions, rebind; verify both report paths.
3. Unbind, add an expendable read-only mass-storage image, rebind; verify keyboard, mouse, and LUN concurrently.
4. Clear the UDC attribute, wait for host disconnect, rebind, and verify clean re-enumeration without stale `/dev/hidg*` state.
5. Reboot the BliKVM with USB-PC attached; verify the composite device disappears and returns, and that host HID/MSD drivers recover.

Log host descriptors, target configfs values, dmesg on both sides, and HID/MSD functional results. Do not use a valuable writable filesystem as an MSD backing store.

