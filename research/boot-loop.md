# Fast build/boot loop

Primary path: **the existing vendor U-Boot plus TFTP**, leaving SPL/U-Boot and the known-good SD untouched.

The actual bootloader was verified to provide Ethernet, `tftpboot`, `dhcp`, and `booti`; its load addresses were read from `printenv` and checked against `bdinfo`. It has no `usb` command, so U-Boot USB storage is not an alternative transport. The full known-good vendor TFTP boot now passes. The shipped U-Boot control DT incorrectly selects PHY address `0x10`; `labctl` applies the guarded RAM-only address-0 correction described in [uart-uboot-tftp-phase.md](uart-uboot-tftp-phase.md).

## Exact first-initramfs command sequence

These addresses and commands apply to the captured vendor U-Boot 2021.10-armbian on this exact board. Do not save them to persistent environment.

```text
setenv serverip 192.168.88.1
setenv ipaddr 192.168.88.2
setenv netmask 255.255.255.0
ping ${serverip}
tftpboot ${kernel_addr_r} runs/000001/Image
tftpboot ${ramdisk_addr_r} runs/000001/initramfs.cpio.gz
setenv ramdisk_size ${filesize}
tftpboot ${fdt_addr_r} runs/000001/sun50i-h616-blikvm-v4.dtb
setenv bootargs "console=ttyS0,115200n8 earlycon loglevel=8 ignore_loglevel printk.time=1 rdinit=/init panic=-1"
booti ${kernel_addr_r} ${ramdisk_addr_r}:${ramdisk_size} ${fdt_addr_r}
```

Verified substitutions are `kernel_addr_r=0x40080000`, `ramdisk_addr_r=0x4FF00000`, and `fdt_addr_r=0x4FA00000`. Saving `ramdisk_size` immediately after its TFTP is essential because every later TFTP overwrites `${filesize}`. The first initramfs should be small enough to remain within the bootloader's observed 64 MiB RAM-disk window and must contain `/init`.

For each run, replace `000001` with an immutable run ID and atomically publish a complete directory only after all artifact hashes are recorded. If `ping` or any TFTP fails, stop at U-Boot; never fall through to stale RAM.

## Automated cycle

```text
build pinned Linux 7.x + DTB + Alpine initramfs
  -> validate Image type, DTB, initramfs, size, hashes
  -> stage immutable run directory under TFTP root
  -> acquire exclusive UART lock and start raw capture
  -> request target reboot (SSH/UART; relay only when available)
  -> detect countdown and send one space
  -> wait for exact U-Boot prompt and record version
  -> send the verified session-only commands above
  -> classify SPL / TF-A / U-Boot / kernel / initramfs / network stages
  -> wait for the initramfs ready marker and serial prompt
  -> execute a serial shell marker and collect dmesg and artifact identities
  -> never auto-save U-Boot environment
```

Timeouts must preserve the console log and leave the board stopped at a prompt where possible. Only explicit operator action may write boot media. SD flashing is reserved for bootloader work/recovery; FEL stays experimental until a RAM-only handoff succeeds.

## Later Ubuntu boot

Once storage/rootfs exists, keep TFTP for `Image` and DTB but change `bootargs` to the stable root UUID, for example `root=UUID=<build-output-uuid> rootwait rootfstype=ext4 ro`. The UUID must come from the built image manifest, never from a copied example. An initramfs may remain for modules and recovery.
