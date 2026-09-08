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

## M8-F0 — MJPEG trailing-byte anomaly isolation (September 8)

**Diagnostic phase only; run 02 remains FAILED verbatim above.** The production
baseline remains `ubuntu-26.04.1-kvmd-msd-baseline`. No JPEG acceptance rule,
frame-rate threshold, continuity threshold, production package, or target image
has been changed. No new 24-hour qualification or P1 work has started.

### Exact preserved-payload analysis

Offsets below are zero-based and identify the first byte of the marker.
The original downloaded payload was independently rehashed on the Build VM.
The explicitly selected binary regression fixture is
`tests/fixtures/m8f0/observed-trailing-data.jpg`; this is the original malformed
payload, **not proven padding**. Machine-readable results are under
`research/evidence/m8f0/analysis.json` and `decode.json`. Separate local analysis
copies are under `out/m8f0/initial/`; nothing was written into run 02.

| Measurement | Result |
| --- | --- |
| Complete payload | 41,448 bytes |
| All FFD9 offsets | `[41434]` |
| Final EOI offset | 41,434; marker ends at exclusive offset 41,436 |
| Trailing length | 12 bytes |
| Exact trailing hex | `0c8fcf214aa5e06389a5d900` |
| Tail all zero | **false** |
| Complete SHA-256 | `d2cd33ac727787d035aef578156fc269a7b796c25b5ff5fb5873c844cf561d3c` |
| Exactly through EOI SHA-256 | `5edc9ede820277d83ed6d282e836e23b07812982317cbe8554f5fc447c62acbd` |

First 64 bytes, hex:

```text
ffd8ffdb004300080606070605080707070909080a0c140d0c0b0b0c1912130f141d1a1f1e1d1a1c1c20242e2720222c231c1c2837292c30313434341f27393d
```

Last 64 bytes, hex:

```text
5140051400514005140051400514005140051400514005140051400514005140051400514005140051400514005140051401ffd90c8fcf214aa5e06389a5d900
```

Installed `libjpeg-turbo-progs` and `python3-pil` on the **Build VM only**.
`djpeg -rgb` independently decoded both complete and EOI-ended files with exit
0 and empty stderr. Pillow also loaded both. All four RGB results have dimensions
1920×1080 and pixel SHA-256
`d71801ead5cdc40294a31a94918d7d5000907a80ccd0fe08c00293e63f1fc872`.
These are separate decoding invocations but both frontends use libjpeg-turbo;
they are not independent codec implementations. Identical tolerant decoding
neither proves padding nor makes the complete payload qualification-valid.

### Pinned upstream length trace

The local upstream archive matches the frozen v6.65 commit
`db87e03ce769d06ba62314ca7537e1cb3369b4de`, archive SHA-256
`af99973b821b1e06ad9dbebc063ceb8ca868e06af7a6ccd90e67dc1d0a7fafea`.
`research/evidence/m8f0/upstream-manifest.json` records inspected source hashes.
Paths and line numbers below refer to that exact upstream archive, extracted
under `out/m8f0/upstream`, before the accepted capture-controls patch.

1. `src/libs/capture.c:395–420`: `VIDIOC_DQBUF` returns the V4L2 buffer;
   multiplanar capture copies plane-zero `bytesused` to the buffer field before
   validation. `_capture_is_buffer_valid` sees that length and mapped data.
2. `capture.c:462`: the selected buffer's `buf.bytesused` becomes
   `hw->raw.used` unchanged. V4L2 timestamp and buffer metadata are also retained.
3. `src/ustreamer/encoder.c:121–123,215–217`: MJPEG selects the HW encoder.
   `encoders/hw/encoder.c:54–87` copies `src->used` bytes. If a Huffman table is
   absent, it inserts the standard table before SOF0 and appends **all** remaining
   source bytes, including any trailing data; otherwise it copies the whole
   source unchanged. Thus the encoded length can be capture length plus the
   inserted table, but no branch canonicalizes the JPEG tail.
4. `src/libs/frame.c:55–70` sets `used` to the copied size and increments it for
   appended bytes. `stream.c:716–730` copies the encoded frame to the HTTP ring;
   `http/server.c:985` copies the selected frame into the exposed frame.
5. `http/server.c:709–718` formats multipart `Content-Length` from
   `ex->frame->used`. Lines 756–759 append exactly that many bytes from the same
   frame, then CRLF and the next boundary. The diagnostic requests normal body
   mode, not `zero_data` or `advance_headers`.
6. The accepted nginx configuration proxies `/streamer/` to this Unix socket
   with buffering disabled. The new observer measures the delivered entity body
   up to the exact advertised multipart boundary independently of the part's
   length declaration; curl handles HTTP transfer coding. TLS/SSH framing is
   outside this multipart entity measurement.

Upstream `capture.c:585–635` first enforces the configured minimum frame size,
then for JPEG requires at least 125 bytes and SOI at offset zero. It accepts any
buffer whose **last two bytes** are `FFD9`, `D900`, or `0000`. Other endings are
rejected unless `allow_truncated_frames` is enabled. It does **not** find a final
EOI or inspect all bytes after it. Its comment describes inexpensive-camera
padding as the rationale; it does not prove any MS2131-specific padding pattern.
The observed payload ends in `D900`, so this shallow validation would admit it
even with truncated-frame permission disabled. This explains an admission path,
not the origin of the eleven nonterminal bytes following EOI.

### Observation-only dual-path diagnostic

`lab/mjpeg-observe.py` and `lab/mjpeg-observe-run.py` are separate from the frozen
soak parser/controller. They never emit a qualification pass and never trim or
rewrite a frame. Body/length discrepancies and strict SOI/EOI failures remain
anomalies while collection continues for neighboring evidence. Split HTTP and
multipart headers, split bodies, and multiple frames per read are supported.

Every complete frame records source path, bridge UTC/monotonic receipt time,
part length and actual boundary-delimited length, SOI/EOI offsets, full tail hex,
first/last 64 bytes, SHA-256, upstream capture/encode timestamps and other part
headers, following boundary bytes, and explicit lifecycle state. Each anomaly
gets its original raw payload, full metadata, previous/next frame metadata, and
an immediately requested read-only target runtime snapshot including uStreamer
PID/start time, exact V4L2 mode, UDC and boot identity. Snapshot time is separate
from receipt time; it is not represented as an atomic capture-time PID reading.

The diagnostic has no scheduled lifecycle disruptions or exemption windows.
The three-second continuity limit, changing-frame five-second windows, and
27-fps 120-second windows remain recorded gates. Any observation failures remain
visible. `lab/mjpeg-observe-compare.py` independently replays those windows and
correlates capture/encode timestamps and payload SHA-256 across direct and HTTPS
paths; a clean bounded observation cannot qualify the soak or establish where
the rare failed payload originated.

Initial fixture validation: 96 repository unit tests passed, including the
exact valid EOI-ended image, observed trailing-data image, arbitrary nonzero
trailer, truncated JPEG, synthetic zero padding (still anomalous), bytewise
headers/body delivery, consecutive frames, a false Content-Length, and continued
strict rejection by the unchanged qualification parser.

The first bounded observation is `qualification/m8f0-observe-01` on the bridge,
unit `blikvm-m8f0-observe-01.service`, requested duration 900 seconds. It uses
one direct Unix-socket client through authenticated SSH and one authenticated,
CA-verified client through the accepted nginx HTTPS LAN path, concurrently.
The bridge supplies the accepted moving-ball 1080p30 source. Target binary
SHA-256 remains
`e5a489c828299bc28de71789414312510198c6d7da63b2b18c300bef6313e71b`;
boot ID remains `febbcc5a-f117-4195-ac10-e77c205c5cae`.
The initial live bridge check found no USB-PC gadget enumeration and target
UDC state `default`; this is not a passing HID/MSD regression.

No canonicalization is justified by the nonzero tail. If direct uStreamer
observation reproduces it, the next diagnostic-only build must instrument the
V4L2 dequeue path before validation/copying, recording buffer index, sequence,
timestamp, bytesused, final EOI, exact tail and first/last bytes without altering
contents. A candidate must not be promoted until capture evidence establishes
the source, bounded stress and frozen HID/MSD/two-client regressions pass, and
no anomalous payload escapes. Only then may a new continuous 24-hour run start
at time zero. Run 02's 14h54m contributes nothing; P1 also requires independent
review of the fresh qualification.

Additional static boundary inspection of the accepted Linux 7.2.3 source:
`drivers/media/usb/uvc/uvc_video.c:1590–1605` removes each isochronous UVC
header and passes `actual_length - header_size` to `uvc_video_decode_data`.
Lines 1360–1380 add the scheduled payload-copy length to `buf->bytesused`;
`uvc_queue.c:365` exports that count through `vb2_set_plane_payload` after the
copy references are released. The driver uses UVC FID/EOF framing, not JPEG
EOI, to complete buffers. This identifies the next instrumentation boundary;
it is static code evidence and does not prove that run 02's tail was present
in USB payload data. No USB trace or capture-buffer dump of that event exists.

### Tail resembles a UVC payload header — hypothesis, not padding proof

The exact 12 bytes also parse as a UVC payload header: `bHeaderLength=0x0c`,
`bmHeaderInfo=0x8f` (EOH, SCR, PTS, EOF and FID set; ERR/STI/reserved clear),
little-endian PTS `2773098959`, SCR clock `2777244640`, and SCR SOF `217`.
The PTS/SCR combination requires a 12-byte header in the accepted kernel's
`uvc_video.c:565–568,597–608`; the flag definitions are in
`include/uapi/linux/usb/video.h:167–174`. Upstream corroboration:
[UVC flags](https://github.com/torvalds/linux/blob/master/include/uapi/linux/usb/video.h)
and [UVC timestamp field decoding](https://kernel.googlesource.com/pub/scm/linux/kernel/git/torvalds/linux/+/c7decec2f2d2ab0366567f9e30c0e1418cece43f/drivers/media/usb/uvc/uvc_video.c).
The decoded hypothesis is archived in `tail-uvc-hypothesis.json`.

This strongly motivates checking for a misplaced UVC header at capture, but
byte-layout compatibility alone does not prove it came from a particular USB
packet or identify whether the device, driver, or later copying misplaced it.
The apparent SOF field happens to be `d9 00`, which explains why this candidate
header also satisfies uStreamer's shallow terminal-byte rule. Do not classify
these timestamp-like, nonzero bytes as deterministic padding or trim them.

The observer archive/negative tests were subsequently expanded to 98 passing
repository tests: they also exercise cross-path hash mismatches, low-rate/frozen
replay failures, and exact raw-payload/neighbor preservation when the runtime
snapshot command fails. The next diagnostic runner snapshots its own sources
at startup and coalesces runtime queries during anomaly bursts to avoid
unbounded SSH process creation. Run 01 retains its original source snapshots.

### Completed bounded observation and continuing collection

Observation 01 completed its 900-second requested interval with no observation
errors or gate violations. Direct: **26,863 frames**; HTTPS: **26,873 frames**.
All **26,863 shared capture/encode timestamp keys** have matching payload hashes.
There were **zero anomalies** on either path. Every complete 120-second replay
window delivered **29.8–29.975 fps**; every complete five-second window changed.
Maximum delivery gaps were **0.09298 seconds direct** and **0.07124 seconds
HTTPS**. This is a clean bounded diagnostic, not a reproduced fault or acceptance.

The complete immutable private archive is
`/home/user/blikvm-msd/m8f0-observe-01-private.tar.gz` on the bridge and
`out/m8f0/m8f0-observe-01-private.tar.gz` on the Build VM: **9,072,095 bytes**,
SHA-256 `66fae2c55872080814a70868996d67d92546c78cd291e53b9ea144c6f32679ac`.
Its 23 files passed the exact qualification-password/private-key/session-header
scan. Authenticated SFTP byte-array transfer preserved the full archive; the VM
verified size/SHA-256, safely extracted it under `out/m8f0/evidence-01/`, and
independently replayed every frame. VM and bridge replay JSON agree exactly.
Selected replay/audit results are in `research/evidence/m8f0/`.

A separate **six-hour observation**, `qualification/m8f0-observe-02`, is running
under `blikvm-m8f0-observe-02.service`, with a 21,600-second collection interval
and 21,800-second outer safety limit. This is M8-F0 observation 02, **not** a
restart or replacement of failed M8-F qualification run 02. Both diagnostic
clients were verified active with over 3,400 frames each and no initial anomaly.
The source, authentication, two paths, strict anomaly classification and gates
are unchanged. No target service restart, target binary replacement, V4L2
capture instrumentation patch, canonicalization, fresh 24-hour qualification,
P1 action, or release commit has been performed.

**Isolation remains incomplete.** No direct anomaly has yet triggered the
conditional capture-instrumentation step. After this collection, inspect both
clients' `result.json`, `anomaly-*` directories and per-frame evidence; compare
matching capture timestamps and raw bytes. If the direct path reproduces the
fault, proceed with the requested diagnostic-only dequeue instrumentation.
Do not promote this clean short sample, the UVC-header hypothesis, or decoder
tolerance into root-cause proof or permission to trim the nonzero tail.

Observation 02's unit entered active state at **2026-09-08 08:26:46 UTC**;
collection should finish around **14:27 UTC**, followed by its final snapshot
and replay. An active/cleanly exited unit alone is not a diagnostic result.
