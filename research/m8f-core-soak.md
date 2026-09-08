# M8-F — 24-hour core KVM integration soak

**Status: qualification FAILED after 14 hours 54 minutes; NOT PASSED.**

Rechecked on 2026-09-08. Run 02 stopped on an unexpected strict JPEG-marker
failure; details are recorded below. P1 remains gated on M8-F acceptance.

Frozen parent: `ubuntu-26.04.1-kvmd-msd-baseline`, commit
`6b2e4217df9d8e66950f960e1a6de6e5c4629e4d`. M6 GPIO/ATX remains **DEFERRED**.
P1 image assembly is gated on accepted M8-F evidence. No physical SD writes
are authorized by this qualification and no full-M8 pass is implied.

## Contract

Consume the accepted Linux 7.2.3 Image/DT, MUSB receive-queue correction,
Ubuntu 26.04.1, M8-C restricted LAN/firewall/TLS/auth policy, one kvmd-owned
uStreamer at MJPEG 1920x1080 with exact reported device interval **30/1**,
keyboard, absolute and relative mice, and strictly read-only G4 media.
No runtime functionality or accepted package/configuration changes are needed.
Writable MSD, GPIO/ATX, optional transports and final read-only-root policy
remain excluded.

## Execution and evidence

`lab/core-soak.py` runs on the discovered LattePanda under a transient systemd
unit, independently of the SSH tool connection. It consumes the frozen
`artifacts-narrow` inputs and references the existing accepted fifth boot.
It verifies that the actual target boot ID matches the archived UART-derived
identity before starting. It never reboots the target.

The bridge supplies the accepted moving-ball 1080p30 HDMI source. A real
Chromium PiKVM Web UI is the first continuous authenticated MJPEG client;
`soak-video.py` is the second. Browser evidence includes normal certificate
trust, connected UI/WebSocket state, authenticated MSD API responses, actual
image dimensions and changing rendered-frame hashes. The second client logs
every frame timestamp, size and SHA-256 with bounded in-memory state.

Every five minutes, the frozen authenticated HID harness grabs the real host
evdev devices and compares keyboard, both mice, buttons and repeated mode
switches against exact expected events, checking released key/button state.
The MSD harness identifies the real USB/SCSI topology, reads the entire
8 MiB medium through O_DIRECT three times before and after eject/attach,
and requires hash
`14845cb5d5d773bc3b7411d2e939b948abc9a7fcc04229159f32a355777ec45b`.
Eject retains the accepted MEDIUM NOT PRESENT semantics; a single documented
UNIT ATTENTION is permitted after attach. No writable operation is enabled.

Read-only resource samples every minute include process PID/start time,
RSS, CPU ticks, FD counts, total process/socket counts, /proc memory/load/CPU,
network counters, TCP SNMP/netstat, exact V4L2 mode, streamer client state,
UDC state and failed systemd units. Baseline/final full policy, ownership and
privilege inventories accompany continuous host/target journals and passive
UART capture. The archive includes the referenced U-Boot/boot evidence,
artifact manifest, source snapshots and dirty Git provenance.

## Schedule and failure policy

The monotonic 86,400-second clock starts after both clients are active.
The target wall clock differs from bridge UTC and is not used for duration.

| Elapsed time | Event |
| --- | --- |
| 4 hours | nginx restart |
| 8 hours | kvmd restart |
| 12 hours | Actual UI logout, denied unauthenticated API, normal re-login |
| 16 hours | Verified DRM DPMS signal loss for 10 seconds and moving-source restoration |
| 20 hours | nginx restart |

Each event has an immutable maximum 60-second disruption/recovery window.
Clients keep collecting evidence throughout. Unexpected disconnects, malformed
JPEGs, frozen video or loss of client heartbeats fail the run; a scheduled
event cannot extend its deadline to hide a failure. Every complete steady
five-second video window requires motion, and independent replay requires
at least 27 delivered fps in every unaffected 120-second window, retaining
the accepted device's exact 30/1 mode. Resources are compared within each
process lifetime as well as across the complete run so restarts cannot hide
growth.

A failure is archived before client/source cleanup. There is no recovery
reboot or automatic userspace repair. Failed pilots remain separate from the
continuous qualification. The 900-second pilot exercises the same actions
at shortened offsets and cannot satisfy the 24-hour gate.

A fresh physical USB-PC reconnect is optional when a live user window is
available. It must use the established monitored procedure and retain
disappearance/recreation, descriptors, host evdev, MSD hash and video recovery
evidence. Do not unplug outside an announced monitored window.

## Acceptance and P1 gate

`lab/verify-core-soak.py` independently replays frame continuity/motion/rate,
raw host evdev records, storage hashes, duration, lifecycle bounds, client
coverage, mode/ownership and resource coverage. Its result remains pending
independent journal and resource-growth review; mere elapsed time is not a pass.
All unexplained persistent USB/UVC/MUSB/SCSI/HID/service errors or meaningful
resource growth must be resolved before acceptance.

Only after all gates and independent review pass, record exactly:
**CORE KVM SOAK PASSED; ATX DEFERRED**.

Then begin P1: inspect the proven vendor disk boot layout, document
`research/image-production-design.md`, build public images twice from frozen
hashed inputs in independent clean assembly directories, verify byte identity
and credential exclusion, and report the proposed P2 flash qualification.
The initial root filesystem stays read-write. Stop at validated artifacts;
do not flash the recovery SD.

## Current run and continuation

The recorded bridge unit is `blikvm-m8f-soak-02.service`, working directory
`/home/user/blikvm-msd`. Evidence is under
`qualification/m8f-soak-02`. The qualification started at
**2026-09-07 06:51:19 UTC**; its 86,400-second interval ends no earlier than
**2026-09-08 06:51:19 UTC**, followed by final inventories and independent
review. It failed before that deadline and is no longer running. Initial
120-second measured delivery was **29.8083 fps**. Both clients,
the first complete real HID/MSD cycle, configured UDC, exact device mode,
UART monitor initialization and healthy systemd state were verified live.
No fresh physical reconnect has been performed in this phase yet.

The unit runs independently of the SSH tool session, has no automatic restart,
and has an 88,000-second outer safety limit. Inspect `progress.json`,
`failure.json` if present, worker heartbeats/results, and the systemd journal.
Do not infer success from an active or successfully exited systemd unit.
The final `result.json` can only say `completed_pending_independent_review`;
it cannot itself release M8-F or enable P1.

After completion, preserve the original per-run directory and run:

```sh
python3 lab/verify-core-soak.py \
  --root qualification/m8f-soak-02 \
  --output qualification/m8f-soak-02-replay.json
```

Review all raw journal candidates, baseline/final resources and every process
generation. Export to a separate private directory with `lab/soak-export.py`,
scan the archive with `lab/msd-audit-archive.py`, download through authenticated
SFTP, verify SHA-256, and repeat replay on the Build VM. Only then decide
acceptance and start P1. A failed gate remains failed and must retain its raw
evidence. The recovery stream replay additionally evaluates full 120-second
windows beginning at declared recovery-window ends, keeping the same 27-fps
threshold when event times do not align with the initial measurement grid.

## Pilot evidence and instrumentation corrections

`qualification/m8f-pilot-01` completed its 900-second exercise plus final checks
without a target reboot. Four HID/MSD cycles, all five lifecycle actions,
changing UI video, two steady-state clients, frozen LUN/device mode and
systemd health passed. Independent recovery windows delivered **29.9583** and
**29.8250 fps**. Host read errors are the four intentional ejected-medium
probes, each with MEDIUM NOT PRESENT and immediate later matching full reads;
they are not unexplained transport failures. Negative HID authentication and
excluded-route probes account for their corresponding target log entries.
One uStreamer broken-pipe message accompanies the planned nginx restart.
The raw bridge log also retains an unrelated host Wi-Fi rekey message.

The 24-hour audit correctly rejects the pilot for duration and resource
coverage. Its passive UART received no bytes, and the original harness did
not create an empty UART file or initialization record. The final controller
creates both before timing begins; the live run confirms their presence.
Additional controller fixes preserve the original event schedule in metadata,
check the two-client count, verify source hashes before running, and write
heartbeats atomically. Startup allowance is recorded separately and does not
exempt any portion of the timed qualification.

The pilot credential scan found session cookies in two verbose Playwright
connection-error call logs. Original evidence was restricted to private access
and qualification sessions were revoked. `m8f-soak-01` was stopped with an
archived interruption reason before its planned lifecycle events; it is
unqualified and contributes no elapsed time to run 02. The browser now scrubs
session headers and passwords before serializing any error or result, with a
dedicated negative regression test. The sanitized pilot copy records original
and redacted file hashes; all measurements remain byte-for-byte unchanged.

The sanitized archive is private on both machines:
`/home/user/blikvm-msd/m8f-pilot-01-sanitized-private.tar.gz` on the bridge,
`out/core-soak/m8f-pilot-01-sanitized-private.tar.gz` on the VM. It is
2,075,465 bytes, SHA-256
`58442f254eff63c43da484119235bff8b5571e50c82c15648af403b80f32d1e6`.
All 345 files pass the exact qualification-password/private-key/session-header
scan on both machines. The text-only SFTP interface did not preserve binary
or Base64 transport; byte-array serialization preserved the archive and the
VM independently verified its exact hash. No world-readable archive was
published. The original and sanitized evidence remain distinct.

Local validation: **92 unit tests passed**, Python/JavaScript syntax checks,
diff whitespace checks, source-hash equality on the bridge, credential scanning
and independent pilot replay on the VM. These qualify the harness preparation,
not long-duration stability. No M8-F acceptance, release commit, image assembly
or physical SD write has occurred.

## September 8 recheck — run 02 failed

The controller detected a stopped video worker at **2026-09-07 21:45:19 UTC**,
53,639.72 monotonic seconds after qualification began (**14:53:59.72**).
The unit exited with status 1. The worker recorded `invalid JPEG markers` at
bridge monotonic time 155288.067820227, outside any planned lifecycle window.
The original `failure.json`, `result.json`, failure-state snapshot, worker
results and raw per-run evidence remain on the bridge. No target reboot or
automatic service repair followed the failure.

The rejected payload `invalid-frame-1603128.jpg` is 41,448 bytes, SHA-256
`d2cd33ac727787d035aef578156fc269a7b796c25b5ff5fb5873c844cf561d3c`.
It begins with SOI at offset 0 and contains EOI at offset 41,434, followed by
12 trailing bytes. The existing parser requires EOI at the end of the declared
multipart payload and therefore rejects these bytes. The payload was
downloaded through authenticated SFTP byte serialization and independently
hash-checked on the VM under `out/core-soak/soak-02-invalid-frame.jpg`.
The complete controller result and marker analysis are retained beside it.
Pillow and command-line JPEG decoders are absent on the bridge/VM, so no
successful independent image decode is claimed. The source of the trailing
bytes remains unproven; no parser threshold or accepted contract was relaxed.

Before failure, 168 complete host-verified HID/MSD cycles passed. All 1,011
recorded direct whole-image reads matched the accepted G4 hash. There are 894
resource samples. The final pre-failure sample reports exact MJPEG 1920x1080,
30.000 (30/1), configured UDC and no failed systemd units. Browser samples
continued to show changing authenticated 1920x1080 video immediately before
controller cleanup. A targeted scan of the full retained host/target journals
found no UVC error, MUSB stall/timeout, USB reset, SCSI timeout/reset, kernel
Oops or OOM candidate; this does not establish the origin of the bad payload
or qualify resource growth.

The 4-hour nginx restart, 8-hour kvmd restart and 12-hour logout/re-login
completed. The 16-hour HDMI event and 20-hour restart were never reached.
The live September 8 read-only check confirms the same target boot ID,
active kvmd/nginx/gadget/MSD-helper services and zero failed units.

**M8-F remains failed; P1 has not started; ATX remains DEFERRED.** Further
work must isolate the payload/transport/parser boundary without changing the
frozen stack or retroactively accepting this incomplete run. A new continuous
24-hour qualification is required after that investigation.
