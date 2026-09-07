# M8-E — authenticated read-only kvmd MSD

**Status: PASSED.** Baseline: `ubuntu-26.04.1-kvmd-msd-baseline`.

Parent: `ubuntu-26.04.1-kvmd-hid-baseline` (`4bb4d7c`).
M6 GPIO/ATX remains **DEFERRED**.

## Ownership and access

The [dedicated ownership record](m8e-msd-ownership.md) documents inspection of
pinned kvmd 4.213's OTG Drive, backend, API and kvmd-otg lifecycle before
implementation. `blikvm-gadget.service` remains the sole configfs creator and
binder. The four frozen functions and all USB/HID descriptors are unchanged.
No kvmd-otg executable/service, second gadget or second storage function is
introduced.

The optional upstream Drive `function` setting retains its original default
and deterministically selects `mass_storage.g4/lun.0` here. A bounded root
media helper performs only attachment and forced eject. Its writable configfs
mounts are exactly this LUN's `file` and `forced_eject` attributes. It validates
the sole gadget, USB identities, UDC parent, four-function configuration,
exact function/LUN, frozen flags, root-owned fixed catalog, and complete image
hash before performing an operation. It never writes mode flags or controls
UDC lifecycle. Its kvmd-only Unix socket checks the peer UID, rejects unknown
fields, paths, identifiers and operations, and has bounded request sizes/timeouts.

kvmd keeps its unprivileged account, no-new-privileges policy, empty
capabilities and frozen video/HID device access. Tests directly confirm it
cannot write any LUN attribute, backing image or MMC node. An unrelated
web-server user cannot connect to the media-helper socket. No sudo, broad
configfs delegation, GPIO or unrelated block-device access is added.

## Approved bytes and upstream controls

The catalog contains only `g4-storage.img`, seeded at build time under
`/usr/share/kvmd-msd/images`, with a root-owned manifest. Both catalog and image
are mode 0444. The original `/usr/share/g4-storage.img` remains byte-for-byte
intact. Static catalog discovery avoids upstream filesystem walking and
remount probes; attachment additionally verifies the full image hash.

| Frozen property | Value |
| --- | --- |
| Image | 8 MiB FAT16 superfloppy; no partition table |
| Label / UUID | `BLIKVM_G4` / `4734-0001` |
| Capacity / logical block | 16,384 sectors / 512 bytes |
| SCSI inquiry | `BliKVM`, `G4 RAM RO`, `0001`, direct-access type 0 |
| LUN flags | `ro=1`, `cdrom=0`, `removable=0`, `nofua=0`, `stall=1` |
| Whole-image SHA-256 | `14845cb5d5d773bc3b7411d2e939b948abc9a7fcc04229159f32a355777ec45b` |
| README.TXT SHA-256 | `59211b2073343cb2384f92cd725e5e7875e2abef83445c41109b249c3244bdff` |
| PATTERN.BIN SHA-256 | `785b0751fc2c53dc14a4ce3d800e69ef9ce1009eb327ccf458afe09c242c26c9` |

The restored upstream MsdApi exposes only GET `/msd`, POST `/msd/set_params`
and POST `/msd/set_connected`. Selection, connection, disconnection and
state changes use the upstream OTG state machine. `rw=true`, `cdrom=true`,
unknown/duplicate parameters, arbitrary paths and remote media fail closed.
Upload, remote upload, remove, download and reset routes are absent. Real
Chromium UI controls support the approved image, connect/eject and state;
excluded controls are hidden and disabled, including before initial state
presentation where applicable.

## Direct API, real UI, authorization and protection

Direct LAN HTTPS uses the exact M8-C listener, development CA, authentication
and bridge-source firewall restriction. Unauthorized state/control and invalid
credentials are rejected. Normal authenticated operations succeed. Logout
revokes HTTP control and closes stale WebSockets; retained media does not grant
continued authorization. Invalid requests leave real LUN state and backing
bytes unchanged, including disconnected RW/path/duplicate-query attempts.

The actual Chromium UI selects the image, connects, ejects and reconnects it.
Independent host checks accompany every UI stage. Host storage is located by
the accepted USB identity, interface 3 topology and SCSI inquiry, never by an
assumed `/dev/sdX`. Capacity, filesystem and both known files match. Full host
reads use O_DIRECT, bypassing the host page cache.

Each storage protection check mounts the exact disposable medium read-only,
requires filesystem create to fail with EROFS, and issues raw SCSI WRITE(10)
to the known image's last sector. The response must be DATA PROTECT / WRITE
PROTECTED. The host device stays read-only. Full direct image reads before
and after reproduce the frozen hash; target checks independently verify both
backing copies and real `ro=1`/`cdrom=0` after transitions. Hashes are checked
before attach, while attached, after rejected writes, after eject and after
reconnect. An API `rw:false` claim alone is never used as the protection gate.

## Lifecycle policy and approved eject clarification

Pinned upstream cleanup does not eject connected media. M8-E retains that
policy across kvmd restart, nginx restart, logout and complete Chromium process
close. On daemon startup, state is reconstructed from the real LUN. Disconnected
selection is transient and may be lost on daemon restart. A clean RAM boot
retains the frozen gadget owner's known G4 attachment; the helper validates
and adopts the identical catalog copy before exposing control. No writable
persistent selection store is added.

The user explicitly approved the E0 clarification: logical eject clears the
backing path and yields SCSI MEDIUM NOT PRESENT plus failed direct reads;
Linux's host block/SCSI objects remain because the frozen USB function remains
present. Actual disappearance/recreation is required for physical USB-PC
unplug/replug. No host-side object deletion, gadget rename, unbind or descriptor
change is used to manufacture disappearance. Reattach may produce exactly one
UNIT ATTENTION, followed by GOOD; arbitrary retry-to-pass is not accepted.

All four connected/disconnected kvmd/nginx restart combinations and normal
recovery are exercised. Planned short HTTP readiness errors are retained.
There is no writable transition, image corruption, stale busy LUN or target
reboot requirement for normal recovery.

## Concurrent workload

The Linux MUSB correction and exact MJPEG 1920×1080 V4L2 interval **30/1** are
unchanged. The accepted moving-ball HDMI source supplies changing video.
Continuous uncached whole-image reads span each measurement while real HID
traffic is verified on the host.

| 120-second client | Frames | Delivered fps | Distinct frame hashes |
| --- | ---: | ---: | ---: |
| Two-client workload, client 1 | 3573 | 29.766 | 3573 |
| Two-client workload, client 2 | 3574 | 29.775 | 3574 |
| Real UI workload, measured second client | 3574 | 29.776 | 3571 |

The paired run completes 254 direct image reads and 12 complete verified HID
API cycles. The real UI workload completes 304 direct reads and 313 browser
HID/session stages, with Web UI video active alongside the measured client.
All read hashes match. Raw frame timing and five-second changing-frame windows
are independently replayed, and resource samples confirm exactly one
kvmd-owned uStreamer. No unexpected USB reset, MUSB stall, SCSI timeout/reset,
HID write failure or persistent service/UVC error appears in accepted evidence.

## Physical USB-PC reconnect

After announcing **READY TO RECONNECT USB-PC** with both monitors active,
the user unplugged and replugged only USB-PC. All three HID event devices,
HID raw/input objects, and host block/sg/SCSI objects disappeared. Enumeration
recreated the four-function topology, with full USB descriptor SHA-256
`733b5003b2c57a865b6366a1e4a8aa6429e9a6d3a827a79b64ba8473b445a52e`
and all three frozen HID report descriptors unchanged.

Selected media stayed attached under the documented policy. Immediate host
reads and SCSI write protection passed, followed by authenticated HID API,
actual MSD UI and HID/browser qualification. The final image hash and LUN
flags still matched. Before/after inventories have the same kernel boot ID
and HID mapping. No manual target repair, software gadget rebind or target
reboot was required to restore operation.

## Five consecutive clean boots

Every final boot uses the corrected helper namespace and the same enrolled
RAM image, SHA-256
`dadf5f2839f42ae062f793a58a79afb5b2305f01e345a4c2434adbaca29467cb`.
Each repeats LAN listener/firewall/TLS/auth, actual API and Web UI, moving
video, keyboard and both mouse modes, media attachment/eject and contents,
filesystem/SCSI write protection, exact gadget ownership, one kvmd-owned
uStreamer, live helper namespace/capabilities, and zero failed systemd units.
All five start with the approved medium connected, as the frozen owner and
validated adoption policy specify.

| Boot | Immutable run ID |
| --- | --- |
| 1 | `20260907T053207Z-unknown-373143` |
| 2 | `20260907T053610Z-unknown-724587` |
| 3 | `20260907T054014Z-unknown-739861` |
| 4 | `20260907T054417Z-unknown-012442` |
| 5 | `20260907T054820Z-unknown-061706` |

All five kernel boot IDs are distinct. These are complete clean RAM boots
through the accepted U-Boot/TFTP path. The vendor recovery SD and persistent
U-Boot environment are unchanged. The earlier two-boot sequence is retained
as superseded following the namespace finding and is not counted here.

## Evidence and reproducibility

[Machine-readable acceptance](evidence/m8e-msd.json) and
[selected public evidence](evidence/m8e-msd/) accompany the implementation.
The complete 5,853,416-byte archive is on the bridge at
`/home/user/blikvm-msd/m8e-evidence.tar.gz` and the VM at
`out/kvmd-msd/m8e-evidence.tar.gz`, SHA-256
`7a9ec724379436e12ffe349b401814a111e83943b471f3a42d5e9b7b44db7917`.
Authenticated SFTP hashes match. All 11,170 archived files passed the exact
qualification-password/private-key/session-header scan. Credentials, private
TLS/SSH material and enrolled images remain outside Git and public evidence.

Independent replay passes 83 full storage protection checks, 243 MSD
state transitions, 23 API/evdev runs, 631 browser HID/lifecycle stages,
three measured video clients, fresh physical reconnect and five complete boot
gates. MSD browser tests separately verify all 11 stages per run. The replay
checks raw event records, frame timing and changing-frame windows, whole-image
read records, real target flags/hashes and exact frozen artifact identities.
The archive retains UART/U-Boot, target dmesg, USB topology/descriptors,
service inventories and both successful and failed developmental runs.

The corrected package, un-enrolled rootfs and initramfs reproduce byte-for-byte
in separate build roots:

| Artifact | SHA-256 |
| --- | --- |
| kvmd-web 4.213-1blikvm4 | `228d2f6dc1114b4516943249d25ddf1f10e4161c9cb53c6603b286b2b4e7f85e` |
| rootfs.tar.gz | `563ed45f6705657b8a52f97e2c5a408c182a5dc5fe9b32ac5af4cdb2d7b97f0a` |
| initramfs.cpio.gz, without private enrollment | `aaf93f7df5da74577bdfa84de2136e8f7f3e38c93f6d008e4407e6c63802d3cb` |

All 88 local tests and Python/JavaScript/shell checks pass. The candidate
checker verifies 341 unchanged inherited runtime files plus the frozen M5
helpers, report descriptors, original G4 image and serializer cases. The
namespace correction changes only the helper service in the package payload.
Source hashes and dirty-parent provenance identify the tested implementation.
Unified-patch context whitespace is preserved. The selected effective-config
export trims only its final blank line; the archive preserves the original.
Build and replay instructions are in [build/kvmd-msd](../build/kvmd-msd/README.md).

## Retained development failures

E0's initial sg_turs/Unit Attention probe remains failed. Implementation
qualification retains two harness failures: a relative mountpoint did not
match absolute mountinfo, and nginx restart briefly refused connections before
readiness. The final inventory initially expected the inherited M8-D package
version and its wrapper swallowed failure output. The corrected harness changes
only that expected version and preserves every inherited runtime check. A live namespace audit also found that systemd left the helper parent configfs
mount writable. An explicit ReadOnlyPaths parent with only the two writable
attribute exceptions corrects that boundary; a new image and complete fresh
qualification follow the correction. Every final boot checks the actual helper
namespace and capabilities. These failures are preserved separately from the final passing runs; they do not
justify changing storage or USB semantics.

## Proposed next slice

A bounded integration soak and reproducible image-production preparation can
exercise the accepted LAN/auth/video/HID/read-only-MSD stack over longer runs,
validate recovery/enrollment and document the image manifest and deployment
procedure. Writable MSD, uploads/deletion/downloads, M6/ATX/GPIO, optional media
transports, VNC/IPMI and final read-only-root policy remain excluded.
