# M5 G4: disposable read-only mass storage

Status: G4 qualified; M5 USB gadget qualification is complete. The accepted
physical run and two consecutive RAM boots below use the corrected MUSB
receive path. Earlier failed and falsely passing attempts remain archived.

G4 starts from frozen G3 commit `520a6eb9809d312045d621500b367a275a42bb3c`,
tag `linux-7.2.3-hid-relative-mouse-baseline`. The keyboard, absolute mouse,
relative mouse, their descriptors and report/event generators remain unchanged.
The separate `gadget-storage` helper calls G3 setup and adds exactly one
`mass_storage.g4` function with its default single `lun.0` before binding.
The product and serial strings intentionally retain the G3 identity.

The only kernel configuration delta is `USB_CONFIGFS_MASS_STORAGE=y`, which
selects `USB_F_MASS_STORAGE=y`. No target SCSI host, loop device, FAT driver,
new controller, device-tree change or rootfs package is needed. The local
Linux 7.2.3 sunxi MUSB FIFO tables provide four or five endpoint pairs; the
three retained interrupt-IN endpoints plus one bulk-IN/OUT pair fit even
the four-pair table. Host descriptor inspection verifies actual allocation.

`build/make-storage-image.py` generates an 8 MiB FAT16 superfloppy using fixed
geometry, volume ID `4734-0001`, label `BLIKVM_G4`, 512-byte logical sectors,
1,024-byte clusters, two identical FATs, and fixed 1980-01-01 file timestamps.
There is no partition table. The complete image is carried at
`/usr/share/g4-storage.img` in the VM-built initramfs; no SD or host filesystem
is used as backing media. The helper checks its size and SHA-256 before
configuring or exposing it. LUN attributes are `ro=1`, `cdrom=0`,
`removable=0`, `nofua=0`; the function uses `stall=1` and SCSI inquiry
`BliKVM / G4 RAM RO / 0001`. No evidence requires CD-ROM emulation here.

| Content | Bytes | SHA-256 |
|---|---:|---|
| Complete image | 8388608 | `14845cb5d5d773bc3b7411d2e939b948abc9a7fcc04229159f32a355777ec45b` |
| README.TXT | 54 | `59211b2073343cb2384f92cd725e5e7875e2abef83445c41109b249c3244bdff` |
| PATTERN.BIN | 1024 | `785b0751fc2c53dc14a4ce3d800e69ef9ce1009eb327ccf458afe09c242c26c9` |

Independent VM `fsck.fat -vn` and `blkid -p` accepted the generated image.
The test suite independently decodes FAT geometry, directory entries, cluster
allocation and file bytes, and rejects extra interfaces/functions.

The bridge verifier selects the USB device by the retained VID/PID/serial,
then resolves exactly one whole disk and its SCSI generic node beneath USB
interface 3. It checks `usb-storage`, `sd`, SCSI inquiry, capacity, logical
block size, read-only state, filesystem identity and all file bytes/hashes.
Mounts use `ro,nosuid,nodev,noexec` and are removed before disconnect tests.
A file-create attempt must fail with EROFS; a SCSI WRITE(10) of one sector to
the last unused sector of the positively identified disposable image must
return DATA PROTECT / WRITE PROTECTED. Complete host hashes before/after and
target backing hashes must match. It never clears the host read-only flag.

The first HIL run `20260906T061720Z-520a6eb-987197` failed during initial
SCSI discovery: the verifier sampled the new disk's temporary `ro=0` before
MODE SENSE completed. Host logs subsequently report Write Protect is on.
The target LUN was already `ro=1` and its backing hash was unchanged. The
bounded disk discovery now waits for all expected properties before returning;
the original failed run and verifier are retained. The normal one-time SCSI
"Power-on or device reset occurred" discovery notification is distinguished
from transport resets/timeouts/errors. No gadget or kernel change was needed.

## Initial result: physical reconnect pending (superseded below)

Run `20260906T061839Z-520a6eb-471976` passed UART/U-Boot/TFTP, MMC/ext4
read-only, EMAC1 and EHCI1/MS2131 discovery; initial and post-software-rebind
snapshots each showed exactly three usbhid interfaces plus one usb-storage
interface. SCSI disk identity, 512-byte logical sectors, 16,384 sectors,
FAT16 identity, file bytes/hashes and full-image hashes passed. The file-create
attempt returned EROFS and SCSI WRITE(10) returned exit 7, CHECK CONDITION,
DATA PROTECT / Write protected. All three retained grabbed HID event tests
passed initially and after rebind. The old block/SCSI objects and input
objects disappeared on unbind; no G4 mount remained.

The runner announced `G4_RECONNECT_READY` and waited 600 seconds. No physical
USB-PC disconnect was observed. It failed at `hid_physical_reconnect` with
`G4 composite did not disconnect`. This is not a qualification pass. Physical
reconnect, post-reconnect storage/HID checks, concurrent 60-frame UVC with
zero startup/stream errors, and two consecutive complete retained RAM boots
remain required. No commit, tag, push or M5 completion claim was made.

The final verifier adds aligned `O_DIRECT` host image reads to ensure each
hash exercises USB storage rather than the host page cache. Separate live
storage-only run `20260906T063027Z-520a6eb-306238` passed direct full-image
reads, filesystem/content verification, both rejected writes, and the target
backing hash afterward. It neither reboots nor binds/unbinds the gadget and
does not substitute for the pending qualification. During the eventual UVC
check, a background direct-read loop will keep reading and hashing the entire
image while all four functions remain active. The physical-attempt verifier
and its prior discovery-race version are both archived separately.

All 48 unit/fixture tests pass on VM and bridge, including direct I/O and
rejection of wrong SCSI identity, writable media and extra interfaces/functions.
All tested executable sources match the VM byte-for-byte. Documentation was
updated afterward. The exact source revisions and dirty state, per-source
hashes and artifact hashes are recorded per run; later changes are not
retroactively attributed to an earlier hardware run.

The byte-exact archive `out/m5/g4-evidence.tar.gz` is 518,707 bytes, SHA-256
`f2ec4ac897a6cbbff67574bfd7230ed0a8850cbe25803bf38a9f2510fae44fcd`.
Authenticated certificate-pinned TLS transfer was verified against the bridge
size/hash. It preserves all three run directories, UART/U-Boot/TFTP logs,
host and target logs, configfs/LUN state, binary USB/HID descriptors, input
events, SCSI/block identity, mounts, rejected-write evidence, file/image hashes,
metadata, results and tested sources. Original runs remain under
`/home/user/blikvm-g4/repo/out/runs/`; VM copies are under `out/runs/`.
[Machine-readable evidence](evidence/m5-g4-storage.json) explicitly records
`not_qualified` and the pending gates. Large logs and binaries stay outside Git.

The four-function gadget remains bound and all HID functions are neutral.
No G4 mount is left on the bridge. The temporary HDMI pattern source was
stopped, VT1 restored and HDMI-A-2 returned to detect mode. The vendor SD,
U-Boot and its persistent environment remain unchanged. Work has not begun
on GPIO/ATX, Ubuntu final rootfs, uStreamer or kvmd.

## Resumed qualification and rejected provisional passes

Physical run `20260906T063326Z-520a6eb-930767` observed the requested cable
removal and recreation, and passed post-reconnect storage and all HID events.
It failed before concurrent capture because a boolean named `concurrent`
shadowed the Python module. The verifier now imports `ThreadPoolExecutor`
directly. A separate live checker verifies physical provenance, unchanged
HID/physical verifier behavior, current descriptor/input/SCSI identity and
backing hashes without rebinding or rebooting. Its source hash and reviewed
verifier differences are recorded explicitly.

Live run `20260906T063650Z-520a6eb-596993` failed on concurrent mount cleanup
and also recorded one startup UVC error. The successful read-only mount was
removed explicitly. Mount/write checks now run sequentially; the concurrent
worker performs only aligned direct image reads. Cleanup detects an actual
mount even if the mount subprocess did not return successfully. A preflight
attempt `20260906T063940Z-520a6eb-792704` also failed because the selected
archived verifier was the older version; the exact source was recovered from
the previously hash-verified VM evidence archive before retrying.

The original result JSON for live run `20260906T064006Z-520a6eb-828174` and
boots `20260906T064116Z-520a6eb-052374` / `20260906T064241Z-520a6eb-909672`
said passed, but **all three are rejected by evidence review**. Each contains
an unexpected host `reset high-speed USB device` message and an approximately
31-second direct read. The initial error matcher missed plain USB resets.
Original logs/results are preserved; the machine-readable review overrides
qualification status rather than rewriting them. The matcher and its
regression test now reject these resets. The normal initial SCSI Power-on
notification alone remains distinct from an unexpected USB reset.

## MUSB receive-queue failure isolation and correction

Observation `20260906T064801Z-520a6eb-045549` captured host usbmon while
reading repeatedly with no reports and during UVC without HID reports.
All reads took about 0.6 seconds. Observation
`20260906T064942Z-520a6eb-540526` then isolated keyboard, absolute, relative
and combined report sequences. Mouse/report activity reproduced 31-second
reads; keyboard-only happened to stay fast in that bounded sample. This is
a timing observation, not proof that keyboard activity cannot trigger it.

The trace records successful 31-byte bulk-OUT command transfers on endpoint
0x01 followed by a pending bulk-IN data transfer on 0x84, cancelled after
roughly 30 seconds and recovered by USB reset. No incorrect file hash was
accepted. Inspection of the pinned pristine Linux archive confirmed that
`musb_ep_restart()` unconditionally flushed the RX FIFO when starting an OUT
request. A packet accepted before its receive request is queued can therefore
be discarded. HID activity changes the timing enough to expose this race.

`board/linux-7.2-musb-rx-queue.patch` replaces that flush with the existing
`rxstate()` receive path, which consumes an already pending packet or waits
for reception. The controller lock and selected endpoint are retained; the
TX path is unchanged. This focused transport correction changes no HID
helper, report descriptor or report behavior. The incremental builder applies
it once to the persistent tree. No clean or mrproper operation was used.

Build `20260906T065248Z-520a6eb-839692` changes only the kernel Image from
the initial G4 artifacts: SHA-256
`b630280ed9063a5be6481fcc877fa423d1b2b3d5de75249da3a3865e49f9de4c`.
The initramfs, configuration, DTB and backing image remain byte-identical.

## Final G4 qualification and M5 acceptance

The corrected-kernel physical run `20260906T065439Z-520a6eb-754257` passed
software unbind/rebind, then a fresh live USB-PC disconnect/reconnect. USB
number 52 disappeared and number 53 returned. All old inputs, the block node,
SCSI disk and generic node disappeared; no stale mount remained. Exactly the
three accepted HID interfaces plus one SCSI/Bulk-Only function returned with
the same descriptor bytes, strings, SCSI identity, capacity and contents.
Post-reconnect file creation failed with EROFS and SCSI WRITE(10) returned
DATA PROTECT / Write protected. Host and target whole-image hashes remained
`14845cb5d5d773bc3b7411d2e939b948abc9a7fcc04229159f32a355777ec45b`.

With USB-PC continuously attached, two full RAM boots then passed
consecutively with the same VM-built artifacts and no intervening failed boot:

| Run | Complete retained stack | Concurrent UVC | Direct 8 MiB reads during UVC |
|---|---|---|---|
| `20260906T065643Z-520a6eb-632211` | UART/U-Boot/TFTP, MMC/ext4 read-only, EMAC1, EHCI1/MS2131, three HID modes, read-only LUN; rebind/content/protection/input passes | 60 non-empty frames, 60 unique hashes, 59 changes, zero startup/stream errors | 8 correct hashes, maximum 0.605 seconds |
| `20260906T065743Z-520a6eb-416769` | Same complete stack and checks | 60 non-empty frames, 60 unique hashes, 59 changes, zero startup/stream errors | 7 correct hashes, maximum 0.618 seconds |

The physical run also delivered 60 non-empty frames, 60 unique hashes,
59 changes, zero startup/stream errors and seven direct image reads below
0.617 seconds. All three grabbed HID sequences passed during capture; all
keys/buttons were released and absolute coordinates returned to zero.
All four functions remained active. Raw host/target log review found no
unexpected reset or persistent USB/MUSB/UDC/PHY/SCSI/storage/UVC error in
these three accepted runs. Their results are independently checked for the
reset signature that invalidated the earlier provisional passes.

The full USB descriptor SHA-256 is stable across the physical reconnect and
both boots: `733b5003b2c57a865b6366a1e4a8aa6429e9a6d3a827a79b64ba8473b445a52e`.
Each boot references the new physical run with identical artifacts and marks
that cable handling was previously verified, not repeated on that boot.

All 50 local tests pass on the VM and bridge. The final tested executable
sources match the VM byte-for-byte, including the MUSB patch. All eight
frozen HID helper/descriptor/verifier files still match G3 byte-for-byte.
Metadata identifies parent `520a6eb` plus dirty state, per-source hashes and
actual artifacts; the later acceptance commit is not attributed to earlier
runs. Documentation was finalized after testing.

Final archive `out/m5/g4-final-evidence.tar.gz`: 3,157,521 bytes, SHA-256
`a056d50f6f636b76b5e560acbae35cb5b418c4f46fd4dcb5b7590bfe86c07e79`.
The size/hash match the bridge after authenticated certificate-pinned TLS
transfer. It preserves all prior failed/rejected runs and verifier revisions,
usbmon isolation traces, final qualification, both boots, exact configfs/LUN
state, host descriptors/input events, SCSI/block/mount state, file/image
hashes, rejected writes, UART/U-Boot/TFTP, host/target dmesg, source snapshots
and machine-readable results. The [summary](evidence/m5-g4-storage.json)
records the accepted runs and explicitly rejects the three old pass flags.
Original runs remain on the bridge and byte-exact copies are under VM
`out/runs/`; verified VM artifacts are added to the three accepted VM copies.
Large raw logs and binary archives remain outside Git.

The accepted slice is preserved by annotated tag
`linux-7.2.3-usb-gadget-baseline`. M5 is complete. The full gadget remains bound
and neutral; all G4 host mounts are removed. The temporary HDMI source is
stopped, VT1 restored, HDMI returned to detect mode. No vendor SD, bootloader
or persistent U-Boot environment write occurred.

## Proposed M6 only; not started

Begin with read-only GPIO discovery through libgpiod and verify chip/line
identity against checked-in vendor wiring evidence. Add line names and
validate power/HDD status inputs against controlled signals. Before driving
power/reset, verify polarity and inactive levels on a meter/test fixture;
then qualify bounded pulses and inactive cleanup. Retain the complete M5
regression stack through each slice. No GPIO/ATX action, Ubuntu final rootfs,
uStreamer or kvmd work is included in G4.
