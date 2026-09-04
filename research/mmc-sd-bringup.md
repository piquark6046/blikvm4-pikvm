# Linux 7.2.3 MMC/SD slice

Status: **passed on real BliKVM v4 hardware** on 2026-09-04. The accepted
serial baseline is commit `969aa19`, tagged `linux-7.2.3-serial-baseline`.

## Vendor evidence and scope

The captured vendor DT and Linux logs identify removable storage on MMC0 only:

- controller `mmc@4020000`, compatible with the H616/A100 MMC block;
- PF0-PF5 `mmc0` pinctrl, 30 mA drive strength, pull-ups;
- four-bit bus and active-low card detect on PF6;
- `vmmc-supply` from PMIC LDO2, named `vcc-sys`, fixed at 3.3 V and always on;
- vendor Linux enumerated `mmc0:59b4 EC1S5` as a 59.7 GiB high-speed SDXC
  card and created `mmcblk0` with partitions p1, p2, and p3;
- the captured `lsblk` identifies all three partitions as ext4, with p1 the
  5.1 GiB vendor root containing Armbian Jammy `/etc/os-release`.

MMC1 is an onboard high-speed SDIO card and is excluded. MMC2 is disabled in
the vendor DT and is also excluded. Linux Ethernet, USB, media, gadget, and
board-control GPIO remain disabled.

The mainline H616 DTSI already supplies the exact MMC0 controller clocks,
reset, interrupt, PF0-PF5 pinctrl, 150 MHz ceiling, and high-speed capability.
The board DTS enables that node, adds PF6 card detect and a four-bit bus, and
connects MMC0 and the PF I/O bank to a fixed 3.3 V `vcc-sys` description.
U-Boot has already established the vendor's always-on rail, so this slice does
not enable the AXP PMIC/I2C drivers or perform PMIC writes.

## Minimal kernel delta

Starting from the accepted allnoconfig-based serial configuration, the only
functional additions are block support, advanced partition selection with
only the MS-DOS parser, MMC core,
MMC block, the sunxi MMC host driver, regulator core/fixed-voltage support,
and ext4. All are built in. The existing build directory remains
`out/build/linux-7.2.3/`; no clean target is used and parallelism remains
`-j3`.

## Read-only automated test

`labctl boot-mmc` uses the proven UART-controlled U-Boot and TFTP path with
session-only environment changes. Each attempt is archived under
`out/runs/<run-id>/`. After the initramfs shell is verified, it:

1. waits for `/dev/mmcblk0p1`;
2. forces every detected `mmcblk` disk and partition read-only with the block
   read-only ioctl and verifies that state;
3. records MMC sysfs identity, `lsblk`, `blkid`, `fdisk -l`,
   `/proc/partitions`, and MMC/regulator/ext4 dmesg lines;
4. mounts `/dev/mmcblk0p1` as ext4 using `ro,noload`, verifies the kernel's
   mount table says `ro`, reads and hashes `/etc/os-release`, then unmounts;
5. captures relevant and complete dmesg plus raw/timestamped UART.

Alpine minirootfs does not include util-linux `lsblk`. To avoid adding a
package set to the small initramfs, `initramfs/lsblk` is a bounded MMC-only
implementation that reports the same required identity fields from sysfs,
BusyBox `blkid`, and `/proc/mounts`.

## Hardware results

Both complete automated attempts passed:

| Run ID | Result |
|---|---|
| `20260904T021821Z-969aa19-190597` | Linux 7.2.3 serial shell, MMC enumeration, partition inventory, and read-only file test passed. |
| `20260904T021906Z-969aa19-622256` | Immediate repeat produced the same device, partitions, filesystem identities, and mount result. |

The card is `mmc0:59b4`, type SD, name `EC1S5`, serial `0x307967bb`, CID
`1b534d454331533530307967bba182ef`, and 125,173,760 512-byte sectors
(59.7 GiB). Linux consistently reported:

- `/dev/mmcblk0p1`: 10,641,408 sectors, ext4 label `armbian_root`, UUID
  `a990fd36-0857-4856-b0b8-5c84a7df516f`;
- `/dev/mmcblk0p2`: 6,144 sectors, ext4, UUID
  `c8699739-a271-4f56-93f8-077b643f9b7c`;
- `/dev/mmcblk0p3`: 114,524,160 sectors, ext4, UUID
  `6e3cffad-01fe-4c59-8635-af31a7e9b7f8`.

Every node reported `ro=1` before the mount. The kernel then logged p1 as
mounted `ro without journal`; `/proc/mounts` reported
`ext4 ro,relatime,norecovery`. The test read Armbian 22.08.2 Jammy's
`/etc/os-release`, recorded SHA-256
`6fa789fc93cec372614e54388116b68edec27915efdeea58de71bc5baaa8f290`,
and unmounted it. No MMC write, filesystem repair, formatting, partition-table
change, persistent U-Boot environment change, or Linux Ethernet/USB enablement
was performed.

Final pre-commit build run `20260904T021601Z-969aa19-347800` used `-j3` and
the persistent `out/build/linux-7.2.3/` object directory. Its artifacts are:

| Artifact | Size | SHA-256 |
|---|---:|---|
| `Image` | 4,024,328 | `232ee349a15741dfbbfbab844c96bd226a3ef91432da2cc498fd17bb335c3760` |
| `sun50i-h616-blikvm-v4.dtb` | 19,532 | `b6488d9ae27f83f8baaff5980e5abe615d926c5752c26f9a3c288d0638ab733f` |
| `initramfs.cpio.gz` | 4,021,686 | `db214238a31d036bea95075007ee5cfdbb97556437f366af1da1984ca2f3c8d4` |
