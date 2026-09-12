# P1 — reproducible standalone SD image production

P1 offline gates passed on 2026-09-12. Public artifacts are in `out/images/`.
No physical SD was written and no standalone hardware boot is claimed.
M8-F core soak is accepted; full M8 is not passed because M6/ATX remains deferred.
The initial standalone root is read-write; final RO/overlay is deferred.

## Design and frozen provenance

[Design](image-production-design.md) was recorded before the assembler was
implemented. [Input lock](../build/image/inputs.lock.json) pins Run 04's exact
public rootfs, Image, DTB, config and package artifacts, plus extracted service,
logging, HID/MSD/G4 contracts and all four production Linux patches.
Acceptance tag: `ubuntu-26.04.1-kvmd-core-soak-baseline`.
Acceptance commit: `4cf664ad3098aca378c65165a29765bffaafa72e`.
Qualified production candidate: `8650c6684b5f8bc0e1b0e0c168ddb5902280484c`.
No Linux, kvmd, uStreamer or accepted rootfs rebuild occurred.

The [assembler](../build/image/assemble.py) makes one DOS partition at 4 MiB,
a fixed 1 GiB ext4 filesystem, a fixed PARTUUID and UUID, and deterministic
boot.cmd/boot.scr. It consumes vendor U-Boot environment load addresses.
Direct root uses PARTUUID because the accepted kernel cannot resolve a
filesystem UUID during early mounting without an initramfs. The accepted
MMC/sunxi/block/DOS/ext4/devtmpfs support is built in. There is no normal RAM
root, TFTP/DHCP command, network root, or deployment-service requirement.

The accepted static LAN policy remains 192.168.88.2/24 with trusted HTTPS
restricted to bridge source 192.168.88.1. Offline enrollment is required for
access to the public base. This is a controlled-lab standalone candidate,
not a generalized first-boot provisioning product.

## Vendor evidence

[Live read-only inspection](evidence/p1/vendor-readonly-inspection.txt),
[layout](evidence/p1/vendor-layout.json), [offline replay](evidence/p1/vendor-replay.json),
[FIT listing](evidence/p1/vendor-fit-list.txt) and [p2 directory listing](evidence/p1/vendor-p2-root.txt)
record the actual medium, not assumed sunxi offsets. Two independent prefix
reads and the VM copy matched. The recovery card was never mounted, repartitioned,
or written. Its entire unpartitioned range is classified: LBA0, zero padding,
SPL, inline FIT and zero padding. SPL checksum and FIT structure/components pass.

Rejected layouts: old raw-prefix copying (stale MBR and p2), GPT (ordinary table
array overlaps observed SPL), full-card mirroring (unneeded 60 GB), and extra
boot/data partitions (no dependency in the proven chain). Vendor p2 contains
only lost+found; p3 is vendor application data. The exact SPL/FIT bytes remain
unchanged; no vendor bootloader compilation/replacement or saveenv occurred.

## Determinism and failures retained

Tools fix UUID, disk ID, hash seed, labels, features, block/inode counts,
SOURCE_DATE_EPOCH, file mtimes, inode creation/access/change times, generations,
superblock times and journal/inode-table initialization. Files retain accepted
numeric ownership, modes, links and payloads except the documented boot/fstab
and public-access delta. Full image bytes are materialized. zstd uses `-19 -T1`.
All tool versions/binary hashes, assembly source hashes and native builder OS
identity are recorded. Compression is independently decompressed and hashed.

Development failures remain under ignored out/p1/: a01 stopped on a valid
literal-backslash systemd filename; a02's offline comparison caught debugfs
interpreting a bare decimal timestamp as a date; explicit @epoch fixed it.
a03 stopped on overly broad password-pattern matches. a04 stopped on library
self-test keys not yet classified. No failed build earned P1 credit. a05 was
a successful development assembly; assembly-A/B subsequently matched with a
complete filesystem manifest including lost+found. Final-A/B freeze the final
tool sources, including the supplemental enrollment scan and private formatter
fix. A private preflight rejected the accepted SSHA512 format before creating
any output; the enrollment validator was corrected to validate that exact format.
The supplemental scanner was tested with injected raw-byte credentials; its
first development iteration was stopped, and only the corrected, negative-tested
scan contributes evidence.

## Credential review and enrollment

Public authorized_keys is empty; the temporary serial autologin override is
removed. Password fields remain locked. No enrolled htpasswd, server/client/CA
private credentials, session state, SSH host keys or qualification archives are
included. The accepted first-boot machine-ID/SSH-key initialization remains.

The full scan includes all regular files, sensitive paths, password fields and
every byte of the raw image, including unallocated areas. Its only exceptions
are exact immutable library constants in [public-constants.json](../build/image/public-constants.json):
OpenSSH's fake NOUSER hash, Passlib's public test/example hashes and GnuTLS
known-answer test vectors. Each exception requires a full file SHA-256 and
exact matched-token hashes; the whole-image counts must equal the filesystem
counts. All 12 GnuTLS key vectors were compared byte-for-byte with the upstream
[3.8.12 self-test source](https://raw.githubusercontent.com/gnutls/gnutls/3.8.12/lib/crypto-selftests-pk.c).
These publicly known constants are not enrolled credentials. The scanner does
not discard unknown matches or exclude binary libraries from scanning.

[Enrollment tool](../build/image/enroll.py) starts from the hashed public image,
and changes only htpasswd, server.crt, server.key and authorized_keys, plus
the necessary ssl directory. Inputs come from the exact Run 04 enrolled overlay.
The CA private key, client private keys and credentials.json are excluded.
Full filesystem comparison preserves every other path/payload/owner/mode/mtime;
raw boot areas stay identical and e2fsck passes. The public base is rehashed.
A supplemental whole-image scan also rejects every supplied enrollment payload,
individual PEM/key lines and any SSHA512 record, independent of location.
The private image, input hashes and transformation receipt remain under ignored
mode-0700 `out/p1/private/`; none is a public deliverable.

## Final artifact evidence

[Reproducibility evidence](evidence/p1/reproducibility.json) records independent
clean assemblies `out/p1/final-A` and `out/p1/final-B`. Whole-file `cmp` and
SHA-256 agree for uncompressed and compressed images and all nine public
output/validation files. There are **zero differing byte ranges**. The copies
in out/images were rehashed and their full allocation verified.

| Artifact | Bytes | SHA-256 (both A and B) |
| --- | ---: | --- |
| blikvm-v4-pikvm.img | 1,077,936,128 | `873845575255879c13dc5a91aebfdbe269929e2af58b3a71c547661776e3c127` |
| blikvm-v4-pikvm.img.zst | 69,962,099 | `80da597e67074fbd55dd4f1ac41f6af63d268e06932c8e59c92005f45bbdf21e` |

[Offline validation](evidence/p1/validation.json) passes all **14,602 filesystem
entries**, exact boot/kernel/DTB/G4/configuration contracts, script header and
payload CRCs, and unchanged before/after image hashes. The loop mount used
read-only plus ro,noload; no physical device was attached by the assembler.
[e2fsck](evidence/p1/e2fsck.log) exits zero through all five passes, using
87,127 of 262,144 4 KiB blocks and 14,496 of 65,536 inodes. Free blocks provide
716,869,632 bytes of measured headroom. The fixed image is not auto-expanded.

The [full secret scan](evidence/p1/secret-scan.json) passes **12,115 regular
files** and all 1,077,936,128 raw image bytes, with zero unexplained hits.
[Additional enrollment separation](evidence/p1/enrollment-separation-scan.json)
checks both builds and the published local copy for actual private enrollment
payloads and SSHA512 material. [Private-image review](evidence/p1/private-enrollment-review.json)
passes 14,606 entries and clean fsck; exactly four enrollment files plus their
SSL parent directory differ. The full private receipt and image are retained
under `out/p1/private/enrolled/`; only the sanitized review is public.

All **134 local tests** pass, including eight P1 tests with injected private
material in raw/unallocated bytes, corrupt scripts and corrupt vendor input.
The [public manifest](evidence/p1/manifest.json) includes frozen artifact,
package/inventory, patch, bootloader, boot-script, filesystem, builder/tool and
complete image hashes. The final [acceptance record](evidence/p1/acceptance.json)
checks all six P1 gates. This is offline production acceptance only.

Limitations: vendor firmware provenance is extraction from the actual card,
not a vendor firmware rebuild; bootloader ext4 parsing, SD root transport,
first-boot machine state, and core regressions on physical SD remain untested
until P2. No finite static scan proves absence of every conceivable hidden
secret, but frozen-input equality, complete filesystem comparison, raw-byte
scanning and actual enrollment-payload absence provide the recorded evidence.
The initial RW root and fixed identities are intentional P1 policy; never
attach multiple clones simultaneously. M6/ATX, full M8 and final RO/overlay
remain unaccepted/deferred.

## Proposed P2 procedure — NOT EXECUTED

P2 requires separate authorization. The known-good recovery SD must stay in the
target while the expendable SD is identified and written on a reader. Keep it
physically separate from that reader throughout flashing. Never identify a
card merely as /dev/sdX, by capacity alone, or by a remembered volatile name.

1. Use `ls -l /dev/disk/by-id`, `lsblk -b -o NAME,PATH,SIZE,TYPE,MODEL,SERIAL,TRAN,RM,MOUNTPOINTS`
   and `udevadm info --query=property --name=<resolved-device>` to identify the
   new expendable card and reader. Record the exact whole-device by-id, its
   resolved path, serial/CID where exposed, capacity and sector sizes. Confirm
   physical labeling. Do not select a `-partN` link. Minimum capacity is
   **1,077,936,128 bytes**; an ordinary expendable 2 GB or larger card suffices.
2. Reject recovery `/dev/disk/by-id/mmc-EC1S5_0x307967bb`, serial `0x307967bb`,
   CID `1b534d454331533530307967bba182ef`, and the bridge system medium
   `/dev/disk/by-id/mmc-DA4064_0x979a962d`. A USB reader may hide the card CID;
   physical separation and positive expendable-card identification remain
   mandatory. Reject any mounted partition, swap, holder, RAID/LVM/crypt member
   or disk backing `/`, `/boot`, `/home` or the image source directory. Stop
   if the identity cannot be proven.
3. Copy the private enrolled image and its private SHA256SUMS/receipt to private
   storage on the flashing host using authenticated SFTP. Verify the full file
   against the receipt before choosing the output device. Never upload it to
   Git, a public artifact store or a public TFTP root.
4. Review and run the guarded commands below only after P2 authorization and
   positive device identification. The typed confirmation binds the exact
   by-id and enrolled-image SHA-256. A placeholder is deliberately not usable.

```bash
set -euo pipefail
P2_SD_BY_ID='/dev/disk/by-id/REPLACE_WITH_VERIFIED_EXPENDABLE_WHOLE_SD'
P2_IMAGE='/private/path/blikvm-v4-pikvm-enrolled.img'
P2_RECEIPT='/private/path/enrollment-receipt.json'
P2_BYTES=1077936128
P2_HASH=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["enrolled_image_sha256"])' "$P2_RECEIPT")
[[ "$P2_SD_BY_ID" == /dev/disk/by-id/* && "$P2_SD_BY_ID" != *REPLACE* ]]
[[ "$P2_SD_BY_ID" != *-part[0-9]* && -L "$P2_SD_BY_ID" ]]
[[ "$P2_SD_BY_ID" != *EC1S5* && "$P2_SD_BY_ID" != *307967bb* && "$P2_SD_BY_ID" != *DA4064* ]]
[[ "$P2_HASH" =~ ^[0-9a-f]{64}$ ]]
[[ -f "$P2_IMAGE" && $(stat -c %s "$P2_IMAGE") == "$P2_BYTES" ]]
printf '%s  %s\n' "$P2_HASH" "$P2_IMAGE" | sha256sum -c -
P2_DEVICE=$(readlink -f -- "$P2_SD_BY_ID")
[[ -b "$P2_DEVICE" && $(lsblk -dnro TYPE "$P2_DEVICE") == disk ]]
(( $(sudo blockdev --getsize64 "$P2_DEVICE") >= P2_BYTES ))
# Abort on any mount or swap; manually reviewed ancestry and physical identity
# from steps 1-2 are additionally required before reaching confirmation.
[[ -z $(lsblk -nrpo MOUNTPOINTS "$P2_DEVICE" | tr -d '[:space:]') ]]
while read -r P2_NODE; do
    [[ -z $(ls /sys/class/block/"$(basename "$P2_NODE")"/holders) ]]
    ! swapon --noheadings --raw --show=NAME | grep -Fxq "$P2_NODE"
done < <(lsblk -nrpo NAME "$P2_DEVICE")
printf 'ERASE only %s with image %s\n' "$P2_SD_BY_ID" "$P2_HASH"
read -r -p 'Type the complete by-id, one space, and SHA-256: ' P2_CONFIRM
[[ "$P2_CONFIRM" == "$P2_SD_BY_ID $P2_HASH" ]]
[[ $(readlink -f -- "$P2_SD_BY_ID") == "$P2_DEVICE" ]]
sudo dd if="$P2_IMAGE" of="$P2_DEVICE" bs=4M iflag=fullblock oflag=direct conv=fsync status=progress
sync
sudo blockdev --flushbufs "$P2_DEVICE"
```

5. Safely remove and reinsert the expendable card into the reader, rediscover the
   same by-id and recheck identity/capacity with no mounted filesystem. This
   prevents a page-cache-only verification. Hash a **complete** readback of the
   written image range; sampling is not sufficient for this small image. Bytes
   beyond the fixed image length on larger cards are outside the image hash.

```bash
P2_DEVICE=$(readlink -f -- "$P2_SD_BY_ID")
[[ -b "$P2_DEVICE" ]]
[[ -z $(lsblk -nrpo MOUNTPOINTS "$P2_DEVICE" | tr -d '[:space:]') ]]
# 257 * 4 MiB is exactly 1,077,936,128 bytes; direct reads bypass page cache.
sudo dd if="$P2_DEVICE" bs=4M count=257 iflag=direct,fullblock status=progress |
    sha256sum > p2-readback.sha256
[[ $(cut -d ' ' -f1 p2-readback.sha256) == "$P2_HASH" ]]
```

If direct I/O is unsupported, stop and review a readback alternative rather
than silently removing it. Archive the write exit status, full readback hash,
image receipt, device identity, byte count and operator confirmation privately.
Read back the partition table and raw SPL/FIT hashes as additional checks.

6. Power the BliKVM fully off. Remove and label the recovery SD and store it
   safely; insert only the verified expendable SD into the target. Disconnect
   Ethernet for the initial boot to prove no TFTP/DHCP service participates.
   Keep UART and USB-PC host observation available. Start a timestamped passive
   115200 8N1 UART capture on rediscovered
   `/dev/serial/by-id/usb-1a86_USB_Serial-if00-port0` before applying power.
   Capture SPL/TF-A/U-Boot distro scan of mmc 0:1, script/Image/DTB loads,
   kernel SD discovery, ext4 root mount and systemd startup without typing
   deployment commands. Never saveenv. Archive the full log, not only success
   markers. Do not interpret compilation or boot-script parsing as boot credit.
7. Reconnect Ethernet after standalone systemd startup. Over the enrolled SSH
   identity record `/proc/cmdline`, `findmnt /`, `lsblk`, `blkid`, `uname -a`,
   boot dmesg/journal, `/sys/class/udc`, exact configfs state, mounted root
   PARTUUID/UUID and RW options. Prove root is the physical SD ext4 partition
   with no RAM-root or network-root dependency. Hash /boot/Image, DTB, helpers,
   G4 and logging configuration against the P1 manifest. Verify a bounded
   disposable write under /var/tmp persists through a software reboot, then
   remove it and record cleanup. Observe the reboot over UART.
8. Validate static Ethernet 192.168.88.2 and the accepted restricted HTTPS
   listener/firewall from 192.168.88.1. Use the existing trusted lab CA and
   normal hostname/certificate verification for `https://blikvm-v4.lab`;
   no insecure TLS bypass. Check SSH host-key provenance through the observed
   console or another explicitly reviewed trust path before accepting the new
   first-boot host key. Verify real Chromium auth/logout, WebSocket and visibly
   changing video; retain API, screenshot and machine-readable evidence.
9. Replay accepted core regressions on SD root: exact MJPEG 1920x1080 30/1,
   unchanged strict JPEG parser and two simultaneous authenticated 120-second
   streams each >=27 fps; sole uStreamer ownership; lifecycle and HDMI recovery;
   real grabbed host evdev keyboard/absolute/relative/neutral HID; approved MSD
   attach/eject, full 8 MiB O_DIRECT reads matching
   `14845cb5d5d773bc3b7411d2e939b948abc9a7fcc04229159f32a355777ec45b`,
   rejected writes and MEDIUM NOT PRESENT on eject. Preserve simultaneous video,
   HID and storage. Capture descriptors, host USB tree/dmesg, target journals,
   bounded logging allocation and exact ownership/privilege contracts. Perform
   an observed physical USB-PC reconnect and a second full standalone cold boot
   with the same checks. Adapt only transport/root-identity checks in the HIL
   harness; retain accepted functional assertions. Archive any failed attempt.
10. On any failure stop qualification, preserve UART/host/target evidence,
    power off and restore the untouched recovery SD. Boot the proven vendor
    chain, or use the existing RAM-only recovery workflow if needed. Never
    repair a failed SD boot by writing the recovery card or replacing U-Boot.
    No M6/ATX, writable MSD, final RO/overlay or new soak is included in P2.

P1 stops at artifacts and this proposal. Standalone hardware boot remains P2.
