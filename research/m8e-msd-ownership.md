# M8-E MSD ownership and E0 decision record

Status: **M8-E PASSED**, frozen at `ubuntu-26.04.1-kvmd-msd-baseline`.
See the [complete bring-up record](m8e-kvmd-msd-bringup.md).
Parent: `ubuntu-26.04.1-kvmd-hid-baseline`, commit `4bb4d7c`.
Date: 2026-09-07. M6 GPIO/ATX remains deferred.

## Pinned source inspection

Inspected kvmd 4.213, commit `387846d22fa807f97de09750c32c1c9b26d36c1c`,
from the existing build archive. Its SHA-256 matches the version lock:
`669a21aafd7e08ca85d02a965a8f3f76b3ba63ac8539ece385b1f676bdf7fdf7`.
The inspected MSD files match that archive byte-for-byte.

* `kvmd/plugins/msd/otg/drive.py`: Drive constructs
  `mass_storage.usb{instance}/lun.{lun}`, reads real configfs state, attaches
  through `file`, and disconnects through `forced_eject`.
* `kvmd/plugins/msd/otg/__init__.py`: the backend selects an image while
  disconnected and applies flags before attachment. `cleanup()` closes image
  transfer readers/writers but does **not** eject connected media. Startup
  reconstructs a connected virtual drive from the real backing-file path.
  A disconnected selection exists only in daemon memory and is lost on restart.
* `kvmd/plugins/msd/otg/storage.py`: default storage discovery uses fstab and
  recursively enumerates files. Its startup probe attempts RW then RO remounts.
  That default probe and arbitrary catalog discovery are unsuitable for this
  seeded, strictly read-only slice and require an explicit static-catalog mode.
* `kvmd/apps/kvmd/api/msd.py`: retain upstream GET `/msd`, POST
  `/msd/set_params` and `/msd/set_connected` semantics. Do not register image
  read/download, upload, remote upload, remove, or reset handlers for this slice.
  Reject `rw=true` and `cdrom=true` before any image-selection side effect.
  The upstream OTG plugin already rejects remote URLs; retain that rejection.
* `kvmd/apps/otg/__init__.py`: upstream lifecycle creates the function and
  grants its user ownership of `cdrom`, `ro`, `file`, and `forced_eject`.
  It also delegates gadget UDC/profile access. Do not use this lifecycle or
  delegation in M8-E.

## Sole owner and privilege boundary

`blikvm-gadget.service` remains the only creator and binder of `blikvm_m5`.
Its frozen M5 helpers create `hid.keyboard`, `hid.absolute`, `hid.relative`,
and `mass_storage.g4/lun.0`. Do not install/start `kvmd-otg`, rename a function,
change configuration links, or grant kvmd gadget lifecycle permissions.

The implemented access mechanism is a bounded root helper with a local Unix
socket available only to kvmd. It is a media-attachment delegate, not a gadget
owner. Keep kvmd's existing unprivileged account, no-new-privileges policy,
empty capabilities and exact device allowances. No sudo grant is needed.
Direct delegation of `file` is insufficient: it permits arbitrary backing
paths, even if `ro` and `cdrom` remain root-owned.

Before each operation, the helper must validate the sole gadget, H616 USB0 UDC
identity, exact four functions/configuration links, exact `mass_storage.g4`
and sole `lun.0`, and all frozen LUN attributes. Only `file` and `forced_eject`
may be written. Never write `ro`, `cdrom`, `removable`, `nofua`, `stall`, inquiry
strings, UDC, or descriptors. Any flag drift fails closed.

The helper must accept a catalog identifier rather than an arbitrary path,
verify a root-owned non-writable regular backing file and its fixed size/hash,
and reject symlinks, traversal, unknown identifiers and extra request fields.
Use a root-owned approved media directory and manifest. Keep the accepted
`/usr/share/g4-storage.img` bytes as regression evidence. Catalog migration
must be explicit and narrowly account for that boot-time backing path before
allowing normal catalog operations; do not allow arbitrary external adoption.

## Small configurable adaptation prepared

[function-name.patch](../build/kvmd-msd/function-name.patch) adds an optional
`function` plugin setting and Drive constructor argument. An empty value keeps
upstream's `mass_storage.usb{instance}` default. `mass_storage.g4` deterministically
addresses the frozen function without renaming it. Function validation rejects
paths, alternate function types and malformed names.

The E0 adaptation is included in `build/kvmd-msd/msd.patch` and the candidate
package. Its function selection alone grants no privileges. The accompanying
bounded helper, static catalog, restricted API and Web UI implement the
read-only boundary and have passed full hardware qualification.

`python3 build/kvmd-msd/check-function-name.py` applies the patch with zero fuzz
to the hash-locked archive and checks default/G4 path resolution, configfs
readback, invalid names and negative LUN rejection. All 82 inherited local tests
also pass. No accepted baseline files were changed.

## Eject gate conflict: directly observed on the frozen hardware

The request's E4/E7 require host block/SCSI objects to disappear on API/UI eject.
Pinned kvmd disconnect only clears the LUN medium. Linux 7.2.3
`fsg_store_forced_eject()` invokes `fsg_store_file(..., "", 0)`, which closes
that backing file and sets `SS_MEDIUM_NOT_PRESENT`; it does not remove the
USB function or host SCSI target. The frozen LUN has `removable=0`.

Two bounded pre-implementation probes preserved all function attributes and
restored the exact original backing image. The second issued raw SCSI TEST
UNIT READY and obtained:

| Observation | Result |
| --- | --- |
| LUN after eject | `file=""`, `ro=1`, `cdrom=0`, `removable=0` |
| Raw SCSI TEST UNIT READY after eject | NOT READY / MEDIUM NOT PRESENT, exit 2 |
| Direct host block read after eject | Rejected with input/output error |
| Host block node, sysfs, sg and SCSI objects | All remain present through repeated samples |
| First TEST UNIT READY after attach | Unit Attention / medium may have changed, exit 6 |
| Next TEST UNIT READY | GOOD, exit 0 |
| Full host image read after attach | Exact frozen image SHA-256 |
| Filesystem create / raw WRITE(10) | EROFS / DATA PROTECT, WRITE PROTECTED |
| USB descriptors before/after | Identical frozen hash |

Image SHA-256 before/ejected/restored/after rejected writes:
`14845cb5d5d773bc3b7411d2e939b948abc9a7fcc04229159f32a355777ec45b`.
Complete USB descriptor SHA-256:
`733b5003b2c57a865b6366a1e4a8aa6429e9a6d3a827a79b64ba8473b445a52e`.

The first probe remains **failed**: `sg_turs` reported bad pass-through setup,
and the old G4 capacity check encountered reattachment Unit Attention. A
separate unchanged G4 regression passed afterward. The second probe preserves
and checks raw SCSI responses explicitly. This is lifecycle evidence, not an
M8-E API/UI pass. No target reboot or gadget rebind was needed for recovery.

**User-approved clarification (2026-09-07):** permit eject qualification through verified
medium absence and failed direct reads, reserving disappearance/recreation of
host objects for actual physical USB-PC disconnect. Do not silently weaken
E4/E7, delete host SCSI objects to manufacture disappearance, or change the
frozen gadget to satisfy those gates. The user accepted this adjustment explicitly; the remaining E1–E11 gates
remain mandatory.

Implemented lifecycle policy: connected media survives
kvmd/nginx restart, logout and browser close; the authenticated control channel
is revoked on logout but that does not eject the medium. Reconstruct state from
configfs after restart. Cold RAM boot retains the frozen owner's known G4
attachment, followed by validated catalog adoption. No persistent writable
selection store is needed.

## Live namespace correction during qualification

A read-only inspection of the running helper's `/proc/PID/mountinfo` found
that `ProtectSystem=strict` plus the two writable attributes did not make the
parent configfs mount read-only. kvmd still had no configfs writes, and the
helper's bounded protocol still rejected arbitrary operations, but this was
broader than the intended helper namespace. The initial five-boot sequence was
stopped after two functional passes; it does not count as E11 acceptance.

The corrected unit explicitly sets `ReadOnlyPaths=/sys/kernel/config` while
retaining only the two attribute exceptions. A live test confirms the parent
and mode attributes are read-only, only `file` and `forced_eject` are writable,
and the helper has exactly CAP_CHOWN with no-new-privileges. API media control
and protection tests pass with this boundary. The candidate is rebuilt and
receives a complete fresh preflight and five-boot sequence. Every final boot
checks the actual namespace, not only the unit text. Both the failed and
corrected namespace inventories are retained.

## E0 evidence and completed qualification

[Selected machine-readable observations](evidence/m8e-e0-eject.json) record
the real transitions and original gate conflict, now resolved by user approval.

Full E0 archive on the bridge:
`/home/user/blikvm-msd/e0-evidence.tar.gz`; VM:
`out/kvmd-msd/e0-evidence.tar.gz`; SHA-256:
`2566d086a7f74647bed55de3225138680f5ccbbef587523b84387809e1ccc793`.
Transferred using authenticated binary SFTP and verified on the VM. The MCP
binary-download rendering was unusable; it was not used as an archive.

The probes use the existing M8-D fifth RAM boot, not a new boot. Its archived
UART/U-Boot/artifact provenance remains in
`/home/user/blikvm-hid/runs/20260907T024038Z-unknown-245573/`.
Probe artifacts retain full target dmesg, real LUN readback, host USB/udev
monitor logs, exact descriptors, SCSI responses and failed/successful storage
regressions. No fresh UART capture or concurrent-video measurement was taken
during the short eject probes; they do not satisfy E9–E11.

After restoration, the unchanged M8-D workload passed 13 authenticated HID
cycles alongside two simultaneous 120-second moving 1080p30 video clients.
Each delivered 3,588 distinct frames at 29.894 fps. This verifies recovery of
the inherited stack; it is not E10, because kvmd MSD integration and continuous
storage reads are not implemented. [Workload result](evidence/m8e-e0-restored-workload.json).
Full archive: `out/kvmd-msd/e0-restored-workload.tar.gz` on the VM and
`/home/user/blikvm-msd/e0-restored-workload.tar.gz` on the bridge, SHA-256
`830c9ab89cbee4c357dd233318f0a4bf7251b3c6eb1084e6e1a3d50f601afaf6`.
Authenticated SFTP hashes match; both E0 archives pass exact credential and
private-key-marker scans.

E1–E11 subsequently passed against the corrected final image, including actual
Chromium, direct SCSI protection, physical reconnect, both concurrent workloads
and five clean boots. The [final evidence record](m8e-kvmd-msd-bringup.md)
supersedes the earlier qualification-in-progress status. Writable media,
upload/delete/download, M6/ATX and later integrations remain excluded.
