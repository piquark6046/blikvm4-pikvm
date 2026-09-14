# P3-S0 MSD runtime-state provenance and fresh-boot invariant

H5R1 remains permanently FAILED at `12680f9f2e4ccd8915ac29a3628a0b8cd3e63bd0`,
with zero P3 credit. Its Chromium functional launch exited normally without
SIGTRAP; the attached-MSD prerequisite was already false before launch.
H3 root cause remains UNASSIGNED. H5 remains FAILED. P2 remains PASSED;
P3 remains UNACCEPTED, P3-B/C blocked, M6/ATX and RO/overlay DEFERRED.

## Preserved current runtime

The [independent replay](evidence/p3/s0-current-replay.json) authenticates all
39 indexed files in private `out/p3-s0/current-empty.tar.gz`, SHA-256
`ce7cf638b5ad02e12de879c145f0a477598d17b4495c5aa5aa9a54fdbb345362`.
Boot `eecefe38-98a3-406c-9260-3e51de321ffe`, physical accepted SD root,
machine/SD identity, service generations and all 10,690 production/enrollment
hashes match the immutable H5R1 failure archive. The LUN file attribute contains
zero bytes; API connected=false while g4-storage.img remains selected.
The immutable flags are ro=1, cdrom=0, removable=0, nofua=0, inquiry
`BliKVM  G4 RAM RO       0001`. Reading forced_eject returns EACCES, retained
as an observation; no attribute was written.

The host retains USB/storage/SCSI objects, ro=1 and a cached 16,384-sector size.
Direct reads fail with zero bytes. That is not a readable 8 MiB medium and the
empty-output digest is not an image hash. Both complete configfs inventory and
all available current-boot journals are private. Journal coverage begins at
monotonic 3.225322 seconds; it is the full retained boot journal, not a claim
that volatile logging preserves every event since power-on.

The first read-only collector stopped on absent bridge lsscsi after target
collection. It remains preserved. The completed collector records that missing
tool and derives host storage identity directly from sysfs. No target repair,
MSD attach/eject, service restart or reboot preceded preservation and replay.

## Immutable archive provenance

The [timeline](evidence/p3/s0-provenance.json) records archive hashes, member
paths, boot IDs, available target monotonic/wall timestamps, archive member
mtime, exact LUN/API observations and available service generations. A missing
field means it was not recorded. Target wall clocks differ from bridge time;
member mtime is evidence-file time, not exact target observation time.

* Accepted P2 and P3-A attempt-01 startup/failure preservation explicitly retain
  the approved attached image. Temporary ejections in completed P2 browser
  protocols are followed by explicit reattachments.
* Attempt-02 preparation preflight 01 ends attached, including its final target
  inventory at monotonic 1423.670086970–1436.904862143 seconds.
* Preflight 02 begins attached and completes ui-connect. The latest explicit
  attached-LUN record is `smoke/browser-msd/ui-connect-after-writes-target.stdout`
  in archive `be15a52352e74b222e219a0ead96f10aa523eefc26d4f4bbe266afa4fad0d644`.
* That archive records a successful Chromium POST
  `/msd/set_connected?connected=false` at target monotonic 1711.896740 seconds,
  wall timestamp 1785186753105334 microseconds. `006.ready` identifies
  `ui-second-eject`; its API observation reports connected=false. The browser
  ultimately records host-stage timeout. The historical classification remains
  the preserved evidence-permission boundary failure.
* The next explicit empty-LUN inventory is
  `inventory/boundary-preservation/target.json`, sampled within monotonic
  1823.818026202–1837.203813000 seconds. H2 and H3 later inventories also
  explicitly record empty. H5 has no direct target runtime observation.
  H5R1 records empty before its first functional browser and after the stop.

The preflight-02 second-eject operation is directly evidenced. No subsequent
reattachment is recorded in the reviewed evidence. Snapshot gaps do not prove
there were no unrecorded transitions. Conservatively:

**historical cause of current empty LUN: UNASSIGNED**.

## Frozen production boot invariant

[Invariant](evidence/p3/s0-boot-invariant.json) SHA-256:
`9cf77f9c6931c383657cbe625c2f640ba77da0ccf7c851b986d056e51280d899`.
It was captured on the bridge before the reboot request.

Captured target `/usr/bin/gadget-storage` and media-helper bytes match the
accepted source and production manifests. Gadget setup creates the sole
mass_storage.g4/lun.0, sets the immutable flags, and attaches
`/usr/share/g4-storage.img`. The helper runs after the gadget; adopt validates
that exact legacy image, then attaches `/usr/share/kvmd-msd/images/g4-storage.img`
before accepting requests. kvmd reconstructs connected state from configfs.
The final catalog pathname, not the transitional legacy pathname, is required.
Both image copies are 8,388,608 bytes with SHA-256
`14845cb5d5d773bc3b7411d2e939b948abc9a7fcc04229159f32a355777ec45b`.

## Preparation reboot

Exactly one ordinary systemd reboot was requested after VM snapshot replay and
passive UART open. It earns zero P3-A credit. No Chromium launch or manual media
operation was used to restore state. The [independent acceptance](evidence/p3/s0-acceptance.json) passes: **fresh production boot restores attached RO MSD invariant**.

Private `out/p3-s0/preparation-reboot.tar.gz` SHA-256
`0032c9ad2c35269e6fdadf0ca158d5167d007866318bffc2c6aa493047cf59fa`
authenticates 100 indexed files. Fresh boot ID is
`1c8365c7-90bf-46fb-8db4-5ec06a745a6a`. All 10,690 hashes match; direct host
reads before and after the guarded final-unused-sector SCSI write match the
complete G4 image. WRITE(10) returns exit 7, DATA PROTECT / Write protected.
One continuous UART segment captures SPL, U-Boot and kernel exactly once,
without TFTP. The target journal review and all retained host kernel messages in the
reboot window show no unexpected filesystem, USB, MUSB or SCSI failure.
H5R2 may now be prepared; its acceptance and P3-A attempt 02 remain pending.
