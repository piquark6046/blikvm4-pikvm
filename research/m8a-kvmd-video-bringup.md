# M8-A minimal video-only kvmd on Ubuntu 26.04.1

Status: **PASSED**, 2026-09-06. M7.5 remains frozen at
`ubuntu-26.04.1-ustreamer-baseline` (`4358af7`), M5 descriptors/storage and M7
kernel/rootfs baseline remain unchanged, and M6 GPIO/ATX remains **DEFERRED**.

## Pinned source and reproducible package

Rechecked upstream on 2026-09-06. The newest published tag is still v4.213,
commit `387846d22fa807f97de09750c32c1c9b26d36c1c`. The prior research snapshot was
verified against live refs rather than assumed current. The pinned
[upstream tree](https://github.com/pikvm/kvmd/tree/387846d22fa807f97de09750c32c1c9b26d36c1c)
and its PKGBUILD/setup.py are the source and dependency evidence. Exact archive:
`https://codeload.github.com/pikvm/kvmd/tar.gz/387846d22fa807f97de09750c32c1c9b26d36c1c`;
SHA-256 `669a21aafd7e08ca85d02a965a8f3f76b3ba63ac8539ece385b1f676bdf7fdf7`.
Live refs and unmodified metadata are in [the evidence directory](evidence/m8a-kvmd/).

`build/kvmd/` assembles `kvmd-video_4.213-1blikvm1_arm64.deb` in the existing
pinned VM builder. It is an explicitly scoped downstream kvmd variant, not the
full PiKVM appliance. The hashed `video-only.patch` removes excluded subsystem
initialization and routes while retaining upstream streamer supervision,
HTTP state/snapshots and WebSocket notifications. It also defers the unused
native shared-memory client import, disables OCR, and identifies BliKVM instead
of Raspberry Pi in system metadata. It does not alter uStreamer's binary or
capture behavior. No alternate video server or invented API replaces kvmd.

The [dependency map](evidence/m8a-kvmd/dependencies.md) classifies core, video,
later HID/MSD, later auth/web and optional integrations. Minimum direct additions
are Python 3.14, PyYAML, ruamel.yaml, aiohttp, aiofiles, setproctitle, Pygments,
evdev constants and Pillow. Ubuntu supplies all native ARM64 extensions; no
separate wheel/native-module build is needed. No pip dependency resolution is
used. The inherited Ubuntu snapshot is `20260906T000000Z`; the full exact
package inventory is enforced by `build/kvmd/packages.lock.tsv`. Patch is a
build-only Ubuntu dependency, absent from the runtime image. The pinned
builder's native dpkg-deb assembles the ARM64 payload.

Two fresh successful package builds and two complete fresh rootfs builds
reproduce identical bytes. The [reproducibility record](evidence/m8a-kvmd/reproducibility.json)
identifies logs, exact sizes, hashes, snapshot inventories and frozen inputs.

| Artifact | SHA-256 |
| --- | --- |
| kvmd-video Debian package | `58db76c4cea63e73182fdce104c808c88dba00393454771907fae2121372770d` |
| rootfs tar/gzip | `97e9fba2674a29bf8f4af6b3c2ac19c66e140243748d5d289cb5e8547d75b0cc` |
| RAM cpio/gzip | `1424e8b3fd65d8702e70f70dc14dabc95a36e524f0d3efa8d4d9bbfffc80643f` |
| runtime package inventory | `37e4a84fb0fc6de0bc3cd7ad5108e5be6a51a1c407a6ab62378f76b603015091` |

The RAM image is 86,475,086 bytes. A separate `lab/kvmd-boot.py` bounds it to
96 MiB at the unchanged `0x4ff00000` address; the exclusive window end
`0x55f00000` is inside verified 1 GiB DRAM and clear of Image, DTB and relocated
U-Boot/reserved regions. Its first monitored boot explicitly qualified the
expanded RAM-only transport. The frozen M7 boot runner retains its 64 MiB
limit. No Image/DTB rebuild, SD write, U-Boot replacement or persistent
U-Boot environment change occurs.

## One streamer owner and minimal service

The pinned `streamer/runner.py` spawns/supervises/kills uStreamer; the manager
queries live state only while its runner is active. There is no supported
external-owner mode. The [ownership decision](evidence/m8a-kvmd/ownership.md)
archives the actual source evidence.

The package stops, disables and masks standalone `ustreamer.service`, changes
only the existing video udev rule's service activation request to kvmd, and
uses `Conflicts=ustreamer.service`. It preserves all four identity predicates,
`/dev/kvmd-video`, the exact `ustreamer=6.65-1blikvm2` package, downstream patch,
binary hash, MJPEG 1920x1080, **30 device fps**, desired 30 fps, native JPEG
quality 0 and HW/pass-through encoder. Its Unix endpoint remains
`/run/kvmd/ustreamer/ustreamer.sock`, mode 0660.

Dedicated user `kvmd` runs with the frozen `ustreamer` device group. Explicit
RuntimeDirectory paths, mode 0750, NoNewPrivileges, restricted writable paths,
AF_UNIX and empty capabilities bound the service. No new sudo policy is
installed; inherited M7 lab SSH/sudo exists solely for qualification. The
service account is denied access to the metadata video node and unqualified
HID/GPIO devices. The frozen kernel lacks BPF device-filter support, so account
and device permissions provide the verified access control; no cgroup BPF
filter enforcement is claimed.

In steady state, kvmd and its one capture uStreamer child occupy the service
cgroup. Upstream metadata queries briefly run `--version`/`--features` probes;
those exit without opening the capture device. Stop and
restart checks verify child cleanup and removal of both sockets. KillMode=mixed
allows upstream cleanup before a bounded systemd cgroup kill fallback.
uStreamer's output is captured by kvmd and appears in `journalctl -u kvmd`;
standalone `journalctl -u ustreamer` has no entries on these new boots.

## Local API and actual video interfaces

kvmd binds only `/run/kvmd/api/kvmd.sock`, mode 0660. Authenticated SSH from the
Build VM through the verified bridge carries target-local API clients. Live
listener evidence shows only the inherited lab SSH TCP listener; video/API
listeners are Unix sockets. There is no nginx, LAN API or web UI.

The pinned API provides `GET /streamer`, `GET /streamer/snapshot`, snapshot
save/load/delete state and `GET /ws` with streamer/client events and ping/pong.
There is no native kvmd multipart `/stream` proxy. `lab/kvmd-api.py` verifies
JPEG decode and 1920x1080 dimensions through kvmd, changing snapshot hashes,
saved-state creation/deletion, live streamer state, BliKVM identity and repeated
WebSocket connections with client counts returning to one on each new session.
Excluded HID/MSD/ATX/GPIO/switch/auth routes return 404. The retained 120-second
multipart test then measures the exact kvmd-owned uStreamer socket; it does
not substitute for those kvmd-facing tests.

Every full HIL run exercises eleven API phases (12 moving snapshots and three
WebSocket sessions each), 120 seconds at >=27 delivered fps, exact independent
V4L2 30-fps readback, three stop/start/restart iterations, three HDMI loss/restore
cycles and frozen keyboard/absolute mouse/relative mouse/read-only MSD checks.
Whole-image storage reads overlap the multipart client. Deterministic
host-verified HID reports run while uStreamer captures continuously and the
kvmd video API is exercised. Device identity, descriptors, configfs, journals, ownership,
listeners, CPU and per-process RSS are archived.

During HDMI absence, MS2131 remains capture-online and emits static JPEGs.
The qualification archives kvmd `/streamer` state and four identical kvmd
snapshot hashes per loss cycle, then requires moving snapshots and frames after
restoration with the same streamer PID and no manual repair. Capture-online
must not be interpreted as HDMI signal detection.

## Hardware results and reboot qualification

| Boot | Qualification | Frames / unique hashes | Delivered fps | HIL run |
| --- | --- | --- | --- | --- |
| 1 | full | 3580 / 3580 | 29.82 | `20260906T113659Z-unknown-191283` |
| 2 | full | 3565 / 3564 | 29.70 | `20260906T114530Z-unknown-281194` |
| 3 | boot_smoke | 3565 / 3565 | 29.70 | `20260906T115402Z-unknown-981789` |
| 4 | boot_smoke | 3565 / 3565 | 29.70 | `20260906T115750Z-unknown-252440` |
| 5 | boot_smoke | 3580 / 3580 | 29.82 | `20260906T120140Z-unknown-966069` |

All five runs pass exact 30.000 (30/1) device-mode readback, local video API and retained M5/M7 regressions. See the [machine-readable acceptance record](evidence/m8a-kvmd.json).

The initial provisional service/API/HIL run is retained separately. After it
passed, two complete clean boots each ran the full qualification. Only after
both full HIL results and the independent reboot audit passed did the bounded
sequence continue with three more complete boots. Each of those repeated
automatic service recovery, kvmd API, the 120-second >=27-fps gate and all
retained gadget regressions. All five boot IDs and the shutdown/U-Boot chains
are independently checked, with one unchanged RAM-image hash throughout.
This is a bounded five-boot qualification, not a 24-hour soak.

Across the five runs, kvmd RSS is 55,184–55,632 KiB and uStreamer RSS is 29,892–30,832 KiB. Combined service CPU averages 3.89–3.94% of one core over 125–126 seconds. The first run has one supplemental child RSS sample; subsequent runs sample both processes throughout. The frozen kernel provides no cgroup MemoryCurrent reading. See [resource samples and limits](evidence/m8a-kvmd/resources.json).

The accepted journals have no ERROR or traceback messages. USB/UVC checks reject
unexpected bus resets and persistent capture errors; the accepted M7 generated-
unit/preset diagnostics remain separate from daemon errors. API disconnects and
HTTP EOF messages are expected consequences of bounded clients.

## Negative and provisional evidence

* First package build failed because the native builder did not contain patch.
  A build-only Ubuntu dependency corrected it; the failed tree/log remain.
* A provisional package preceded the corrected explicit OCR exclusion and DT
  serial handling; it is not the accepted package.
* The first rootfs wrapper was edited while executing and failed at final
  bookkeeping. Its payload was reserved for provisional HIL. Two later complete
  fresh builds pass and reproduce its bytes; the failed wrapper is not counted
  as a successful reproducibility run.
* The no-signal evidence parser was corrected to parse kvmd's actual multiline
  JSON followed by hashes, before the independent acceptance audit. A local
  regression test covers this native response and rejects missing/static-state
  mismatches.

The per-run archive records actual HIL automation hashes. Later validation-only
changes add direct kvmd no-signal checks, whole-cgroup process counts and child
RSS sampling. They do not change the tested package/rootfs payload. Raw logs
retain target RTC timestamps independently of bridge UTC; duration and rate
gates use monotonic time.

Complete local archive: `out/kvmd/m8a-evidence.tar.gz` (4,730,209 bytes), SHA-256 `f790eb382b6ecc61f9c1c9351cae347d2ba37c0d3ed72630a0bbc34a5491a14d`. It includes immutable bridge runs, UART/U-Boot, API/JPEG and gadget evidence, plus pinned source, VM build logs (including negatives), payload manifests and automation. Selected reviewable evidence is checked in under `research/evidence/m8a-kvmd/`; large raw run logs remain in the archive. Authenticated SFTP transferred the bridge archive and the VM verified its hash before replaying the acceptance audit. All 70 local tests pass. Generated build manifests retain their pre-HIL status; the separate acceptance record combines successful reproducibility and hardware gates. The HIL checkout records parent `4358af7` plus dirty/new-source hashes; the annotated baseline commit captures the reviewed implementation.

## Scope boundary and next slice

M8-A stops at video-only kvmd. M6 remains deferred. No nginx/web UI, external
network exposure, PAM/htpasswd auth, kvmd HID/MSD/ATX control, Janus/H.264/VNC/IPMI,
Wi-Fi/OLED or final read-only-root policy is enabled.

Proposed M8-B: qualify local web delivery and explicit authentication over an
SSH tunnel first, preserving this exact video owner and frozen gadget paths.
Pin/package only the selected web/auth dependencies and test access control,
logout/session behavior, reconnect and reboot before separately authorizing any
LAN exposure. HID/MSD/ATX control remains a later independent slice.
