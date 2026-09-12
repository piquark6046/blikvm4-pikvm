# P1 standalone image design

Design frozen before assembler implementation, 2026-09-12. P1 is offline image
production only. M8-F core soak passed; M6/ATX and final RO/overlay remain deferred.
No physical SD write, reboot, U-Boot replacement or saveenv is authorized here.

## Accepted inputs

Acceptance tag `ubuntu-26.04.1-kvmd-core-soak-baseline` resolves to
`4cf664ad3098aca378c65165a29765bffaafa72e`; qualified candidate is
`8650c6684b5f8bc0e1b0e0c168ddb5902280484c`. Run 04's artifact-hashes.json
is authoritative. Consume its public rootfs tar, Image, DTB, config, and frozen
kvmd-web/uStreamer packages without rebuilding them. Verify extracted logging,
HID/MSD helpers and both G4 paths against the frozen tar and prior contracts.
Archive hashes of all consumed inputs; any mismatch stops assembly.

## Vendor extraction and layout

Read-only SSH inspection through the rediscovered LattePanda found the recovery
card at target `/dev/disk/by-id/mmc-EC1S5_0x307967bb`, CID
`1b534d454331533530307967bba182ef`, 64,088,965,120 bytes, 512/512 logical/physical
sectors. All its partitions were unmounted on the accepted RAM root. Two separate
4 MiB reads match SHA-256
`97370d2c6ba452ebb445fe1b637703c09cfadc2eb2c131f4510145050b9e5669`.
Authenticated SFTP to the VM was checked against the configured bridge host key.
The prefix includes p2 and is private inspection evidence, not an image input.

[Vendor layout](evidence/p1/vendor-layout.json) records every partition, extent,
filesystem identity, component hash and FIT properties. DOS table ID is
`6a80d8d9`. LBA0 is partition metadata, not the Allwinner boot payload.

| Object | Absolute byte offset | Bytes |
| --- | ---: | ---: |
| LBA0 (excluded from copy) | 0 | 512 |
| eGON SPL, validated header length and checksum | 8192 | 40960 |
| FIT, validated FDT total size | 49152 | 608135 |
| U-Boot inline FIT data | 49336 | 535904 |
| TF-A inline FIT data | 585392 | 49265 |
| U-Boot board DTB inline FIT data | 634936 | 21064 |

The FIT selects `config-1`, firmware `atf`, loadables `uboot`, and `fdt-1`.
TF-A is contained in the FIT; it has no separate raw extent to copy. The data
property interpretation follows the [U-Boot FIT format](https://docs.u-boot-project.org/en/v2023.10/usage/fit/source_file_format.html).
SPL version/board strings and FIT descriptions agree with the archived UART
chain (SPL/U-Boot 2021.10-armbian, TF-A v2.8). This is provenance from the actual
recovery medium, not a reproducible build of vendor firmware.
Bytes [512,8192) and [657287,1048576) are all zero. All space after 1 MiB is
covered by the vendor's three contiguous ext4 partitions (in physical order
p2, p1, p3), through the last sector of the card. Thus no other raw boot
structure exists in the unpartitioned area. p2 is an empty ext4 filesystem
containing only lost+found. p3 supplies vendor application data at /mnt;
boot.scr reads p1 and the accepted production userspace has no p3 dependency.

## New disk and filesystem

Use DOS/MBR with fixed disk ID `b14b0001`, one type-83 partition starting at
sector 8192 (4 MiB), size 2,097,152 sectors (1 GiB), bootable. Total image length
is 1,077,936,128 bytes (1028 MiB). The root tar has 14,598 entries and
321,499,458 regular-file payload bytes before hardlink savings. A 1 GiB root
leaves over 600 MiB for filesystem metadata, enrollment, runtime state and
updates; it is fixed and never auto-expanded in P1. No swap partition.
Root UUID `b14b0001-2026-4001-8001-000000000001`, label `blikvm-root`,
PARTUUID `b14b0001-01`. Do not attach two clones to a target simultaneously.

Reject copying a raw prefix: it would copy the old table and p2. Reject GPT:
its ordinary primary array overlaps the observed SPL at 8 KiB and adds no
needed feature. Reject mirroring 60 GB, separate /boot, p2 and p3: none is
needed by this chain. Copy only the exact two hashed bootloader extents into a
new zero-filled image with a newly constructed MBR. Published hashes cover
every logical byte; materialize zero ranges and verify allocated file size.

Use ext4 with explicit conservative features supported by the vendor U-Boot:
has_journal,ext_attr,resize_inode,dir_index,filetype,extent,sparse_super,
large_file,huge_file,uninit_bg,dir_nlink,extra_isize. Omit newer orphan_file,
metadata_csum_seed and 64bit for boot-reader compatibility. Keep a journal
and initial RW root. Fix UUID, hash seed, inode count, block/inode sizes,
reserved blocks, mount options and timestamps. Fully initialize inode tables
and journal. Normalize inode atime/ctime/mtime/crtime and generation; fix
superblock creation/check/write times using the e2fsprogs fake-time facility.
The hash seed and initialization controls follow [mke2fs](https://man7.org/linux/man-pages/man8/mke2fs.8.html).
SOURCE_DATE_EPOCH is the accepted Ubuntu build epoch `1788652800`.
Byte-identical independent A/B builds are mandatory, not an assumption.

## Boot

Keep BootROM -> vendor SPL -> TF-A -> vendor U-Boot -> distro mmc 0:1 ->
/boot/boot.scr. Boot script loads accepted /boot/Image and
/boot/sun50i-h616-blikvm-v4.dtb using existing kernel_addr_r/fdt_addr_r, with
nested success checks and no network command. On failure, halt the script's
execution loop rather than falling through to network boot targets.

Kernel command line:
`console=ttyS0,115200n8 earlycon loglevel=6 printk.time=1 root=PARTUUID=b14b0001-01 rootfstype=ext4 rootwait rw net.ifnames=0 panic=-1`

The accepted config builds in MMC, MMC_BLOCK, MMC_SUNXI, MSDOS_PARTITION,
and EXT4_FS. Its block/early-lookup.c supports PARTUUID but does not resolve
filesystem UUID at early mount, so use PARTUUID for direct root without an
initramfs. /sbin/init is the accepted systemd entrypoint; rdinit is unnecessary.
/etc/fstab names the same root PARTUUID with ext4 defaults and fsck pass 1.
No TFTP, DHCP, VM or bridge service is required to load or mount root. Existing
static LAN settings and source-restricted HTTPS remain accepted lab policy.

## Public base and private enrollment

Preserve all accepted package/config payloads except an explicit transport and
credential delta: add boot files and fstab; empty authorized_keys; remove the
temporary serial autologin drop-in. Leave locked password fields, no TLS keys,
no htpasswd or session secrets, no SSH private keys and no qualification logs.
Keep the accepted uninitialized machine-id marker so systemd creates per-device
state. The public base intentionally needs enrollment for authenticated access.

Offline enrollment starts with the exact hashed public image and replaces/adds
only an explicit list (plus creation of the necessary root-owned mode-0755
/etc/kvmd/nginx/ssl directory): /etc/kvmd/htpasswd, /etc/kvmd/nginx/ssl/server.crt,
/etc/kvmd/nginx/ssl/server.key, /home/blikvm/.ssh/authorized_keys. Reuse the
private Run 04 enrollment with recorded provenance. Client SSH private keys,
CA private keys and credentials.json never enter either target image. Target
SSH host keys remain generated by the accepted service at first boot.
Private images and transformation receipts stay in ignored mode-0700 storage.
Compare full filesystem manifests; only approved enrollment files may differ,
plus necessary inode/allocation metadata. No service/policy drift is permitted.

## Offline validation, recovery and P2

Extract each partition from each image into regular files (equivalent read-only
image inspection); e2fsck -fn must be clean. Validate the table, raw extents,
script header/CRCs, root identity, full filesystem metadata and payloads, package
inventory, logging, G4 and absence of diagnostics/private material. Use read-only
loop mounts with ro,noload where available, never a physical device.

Recovery is the untouched known-good SD. P2 must positively identify an
expendable whole SD by /dev/disk/by-id, reject the recovery CID/serial and any
system disk or mounted device, require capacity >=1,077,936,128 bytes and an
explicit destructive confirmation. Write only a verified private enrolled
image, flush, remove/reinsert into the reader and hash a complete readback of
exactly the image byte count. Then power down target, insert expendable SD,
observe full standalone UART boot without Ethernet deployment infrastructure,
and validate RW SD root, Ethernet/trusted HTTPS, browser video, real host HID
and read-only MSD including reconnect/reboot regressions. On failure preserve
UART/dmesg and restore the recovery SD with power off. Exact proposed commands
and evidence requirements will be recorded in p1-image-production.md. P1 does
not execute P2 or claim standalone boot, full M8, or M6/ATX acceptance.
