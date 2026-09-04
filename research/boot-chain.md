# Boot chain

## Verified vendor flow

```text
H616 BootROM
  -> SD boot signature (current board: removable SD, MMC0 in U-Boot)
  -> U-Boot SPL 2021.10-armbian (DDR init: 1024 MiB)
  -> TF-A BL31 v2.8 debug build (PSCI/EL3)
  -> U-Boot 2021.10-armbian
  -> distro scan of mmc 0:1
  -> /boot/boot.scr generated from /boot/boot.cmd
  -> Image + legacy uInitrd + sun50i-h616-mangopi-mcore.dtb
  -> Linux 5.19.4-sunxi64
  -> Ubuntu/Armbian initramfs
  -> ext4 root by UUID on mmcblk0p1, remounted read-only
  -> systemd + BliKVM services; writable application/data partition on mmcblk0p3 at /mnt
```

The BootROM's exact media priority was not destructively tested. Upstream documents SD/eMMC boot signatures at 8 KiB and, for newer SoCs, 128 KiB, then FEL when no valid boot image is found. The current board directly printed `Trying to boot from MMC1` in SPL and `U-boot loaded from SD` in the boot script.

## Verified bootloader facts

- U-Boot proper, SPL, and TF-A versions and build dates are preserved in [vendor-system/uboot.txt](vendor-system/uboot.txt).
- DRAM window: `0x40000000-0x7fffffff` (1 GiB).
- Runtime addresses: `kernel_addr_r=0x40080000`, `fdt_addr_r=0x4FA00000`, `ramdisk_addr_r=0x4FF00000`, `scriptaddr=0x4FC00000`.
- Kernel format is an uncompressed AArch64 `Image`; U-Boot moved it from `0x40080000` to `0x40200000` before entry.
- The installed initramfs is a legacy U-Boot gzip image, but `booti` explicitly supports a raw initrd as `address:size`.
- The compiled environment tries to load a FAT environment and reports `Unable to use mmc 0:1`; discovery therefore treated `printenv` as compiled/runtime defaults and did not call `saveenv`.
- Boot targets are `fel mmc0 pxe dhcp`. `tftpboot`, `dhcp`, `booti`, `load`, `ext4load`, and `fatload` exist. U-Boot `usb` commands do not.
- Ethernet in U-Boot is `ethernet@5030000`, MAC `02:00:eb:b5:cf:cd`.
- SD is the only listed U-Boot MMC device. Linux's vendor DTS disables MMC2/eMMC.

## Security/recovery observations

No secure-boot enforcement or signed-kernel check appeared: U-Boot executes a normal boot script and `booti`. That does not prove eFuse state. TF-A logs a failed AXP305/RSB probe but the known-good system remains stable; this reinforces that the PMIC description in old firmware is not a template to copy blindly.

The safe baseline recovery is the current known-good SD image. Before any write, image the card using its by-id/topology/size identity and verify the backup. Do not replace SPL/U-Boot until kernel, DTS, network, and recovery paths are working.

