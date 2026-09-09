# M8-F0 uStreamer diagnostic instrumentation

Current work: [harness revision 2](HARDENING.md). The historical Observation 03
plan below is superseded by the confirmed DQBUF gate: after harness preflight,
proceed directly to a separate Linux uvcvideo diagnostic.


Status: **hardened ARM64 harness preflight PASSED; original preflight remains FAILED**.

The following failed-preflight description is historical and retained. Current
evidence and limits are in [harness revision 2](HARDENING.md).

Observation 02 completed, was privately archived/transferred/independently
replayed, and supports exactly Branch A. The separate diagnostic ARM64 RAM
image then passed stream/HID/MSD/resource checks but failed the required
coverage gates: three suppressed DQBUF events, consumption of the four-raw-frame
allowance, and root-owned flush requests rejected by the writer. No retry or
kernel diagnostic was started. The complete result, archive hashes and bounded
DQBUF proof are in [M8-F0 status](../../../research/m8f-core-soak.md).
`lab/mjpeg-taildiag-preflight.py` and `lab/mjpeg-taildiag-runtime.py` retain the
failed-run harness; **do not reuse their root-owned flush path as an observation
03 launcher**. The offline preparation procedure below remains source evidence,
not a passing runtime preflight.
M8-F0 remains OPEN. Qualification run 02 remains permanently FAILED and supplies
zero time to any new qualification. P1 stays gated; M6/ATX stays DEFERRED.

`jpeg-tail-diagnostic.patch` applies **after** the frozen capture-controls patch
to uStreamer v6.65 commit `db87e03ce769d06ba62314ca7537e1cb3369b4de`.
It is deliberately absent from the accepted package/rootfs recipes and pins.
`taildiag.c` and `taildiag.h` are the readable helper sources included verbatim
in the patch; `prepare.py` checks they agree after application.

## Offline preparation and tests

From the Build VM repository root:

```sh
python3 build/ustreamer/diagnostics/prepare.py --output out/m8f0/next-diag-source
python3 -m unittest discover -s tests
```

The output directory must be new. Preparation checks the upstream archive and
accepted patch hashes, applies both patches without fuzz, and records Git and
strict-parser hashes in `diagnostic-source-manifest.json`. It never uploads,
installs, restarts a service, or opens a device. Do not use the production
`build/ustreamer/build.sh` to install this candidate.

The helper uses OpenSSL SHA-256 (`libssl-dev` build dependency, `libcrypto`
runtime dependency) in addition to existing uStreamer dependencies. Native
fixture tests require `cc`, pthreads and the OpenSSL headers/library. A future
ARM64 diagnostic artifact must be built on the VM in a separate pinned build
root, record exact dependency versions/hashes and executable hash, and remain
distinct from `6.65-1blikvm2`. The native validation executable is **not** a
candidate to copy onto ARM64. No production package/configuration pins change.

## Boundaries and semantics

1. `capture.c`, after successful `VIDIOC_DQBUF`, checked buffer index, and plane
   zero length normalization, immediately before `_capture_is_buffer_valid`.
   Only JPEG formats are inspected. The length must fit the existing mapping.
   Every dequeue is observed, including frames upstream later rejects/skips.
2. HW encoder, immediately after `_copy_plus_huffman` returns. This observes
   both the whole-copy and DHT-insertion paths with their original results.
3. HTTP exposed frame, immediately after `us_frame_copy`, before fan-out.
   Existing multipart headers/lengths, copies, retries and client logic remain
   byte-for-byte unchanged. The new offline `lab/mjpeg-taildiag-correlate.py`
   joins these records to the existing observer without changing that observer.

No hook returns a decision. No hook modifies frame data, lengths, timestamps,
validation, retry policy, device FPS, quality, or HTTP behavior. It preserves
`errno`. Original HW-JPEG DHT insertion remains intact; it can change the hash
between dequeue and encoding, so unequal hashes there alone are not a bug.

Each accepted anomaly has hook-time realtime/monotonic timestamps, stage/PID,
V4L2 index/sequence/flags/timestamp/reported bytesused, current bytesused, first
SOI, **every raw `FFD9` offset**, final raw EOI, exact tail length/hex, first/last
64 bytes, whole SHA-256 and SHA-256 through the final EOI. Offsets are zero-based
at the `FF` byte. A structural marker walk skips segment contents and stuffed
entropy data to exclude an incidental `FFD9` inside APP/COM data without a
real terminator. It does not decode pixels or replace the qualification parser.
The final raw EOI controls the tail extent, matching existing observer analysis;
all marker offsets remain available when there are multiple EOIs.

The UVC classifier reports length, all bmHeaderInfo flags, PTS, SCR clock/raw
SOF/11-bit SOF/reserved bits, minimum field length, field completeness, and
whether the declared length equals the entire tail. Extension bytes are allowed
in a header-shaped candidate. `header_shaped_only` is **layout evidence only**,
never provenance, padding classification, permission to trim, or JPEG acceptance.
The preserved tail `0c8fcf214aa5e06389a5d900` is the strongest current hypothesis.

## Bounded evidence and limitations

The diagnostic is opt-in with `USTREAMER_TAILDIAG_DIR`, pointing to a new,
existing private directory owned by the running uid (mode 0700). All output
files use exclusive creation, no-follow, and mode 0600. Reusing a directory
with `session.json` disables diagnostics instead of overwriting evidence.
Missing/invalid directories also disable diagnostics; check `session.json`
and actual process environment before relying on a future observation.

There are four preallocated 8-MiB payload slots (32 MiB maximum heap payload
reservation), 2,048 recent boundary summaries, at most 64 records per boundary,
and at least one monotonic second between records at each boundary. At most
the first four accepted anomalous payloads per boundary are saved whole.
All accepted records retain the exact complete tail, even without a raw dump.
A conservative 128-MiB process-wide disk reservation bounds metadata plus raw
payloads; records that cannot fit are suppressed. Frames exceeding 8 MiB or
mapping capacity are counted without reading their bytes. These limits apply
to diagnostics only and never cause capture/HTTP rejection.

The capture/encoder/server threads scan/hash normal frames and retain their
bounded summaries, but do not write files. They copy only admitted anomalies
into the queue; one writer computes detailed marker/tail records and performs
file I/O. Normal earlier-boundary hashes/lengths/suspicion flags are attached to
later anomalies, allowing a clean dequeue to be distinguished from a copy-origin
anomaly. Producer work includes scanning, hashing, a short mutex section and
bounded anomaly copying. Instrumentation has measurable overhead and still
needs runtime FPS/resource checks; unchanged settings do not prove unchanged
throughput. The writer never holds the mutex across disk I/O.

Correlation uses uStreamer's existing millisecond-quantized capture timestamp,
formatted to six decimals exactly as its multipart header. HW/exposed events
also carry the existing encode-end timestamp. Later V4L2 metadata is recovered
from the recent capture summaries, not invented from HTTP receipt time. A
missing recent match is explicitly null. Duplicate matches set
`correlation_ambiguous` and are not used to assign V4L2 identity. Ring eviction
requires review; missing records cannot prove a boundary was clean. Scope is
one positively identified uStreamer child/capture stream per evidence directory.

`summary.json` on normal process exit reports inspected/suspicious/admitted/written/suppressed,
invalid-length and missing-metadata counters. Missing summary, unequal admitted/written counts,
partial files, exhausted limits or suppressed events are evidence gaps, never
a clean-run conclusion. Abrupt kill/power loss can leave queued events unwritten.
For observation 03 only, put an empty `flush.request` in this private directory
as the **first** action of the multipart observer's anomaly context command,
before its slower runtime inventory. The writer checks once per second and
preserves up to four `recent-NNN.json` snapshots (normal metadata/hashes only),
within the same disk budget. Snapshot request time and attempted/written counts
are archived. At roughly 90 boundary calls/second the ring spans about 23 seconds;
late requests/ring eviction remain evidence gaps. The existing observation 02
runner/context command is untouched. The offline correlator joins these normal
snapshots to delivered anomalies, covering a fault first appearing after HTTP
exposure without continuously logging normal frames.

On recurrence, preserve already-written data before terminating collection;
use the application's normal shutdown to drain the queue, then archive counters.
Do not run a new candidate merely to overwrite/retry a failed diagnostic run.

Offline correlation (new output path):

```sh
python3 lab/mjpeg-taildiag-correlate.py \
  --diagnostics /path/to/archived/target-diagnostics \
  --clients /path/to/archived/observation-03/clients \
  --output /path/to/new/correlation.json
```

This verifies saved diagnostic payload hashes/lengths/tails and matches existing
multipart capture/encode headers. It reports matches and gaps; it does not
choose a fix, emit qualification acceptance, or replace independent replay.

## Observation 02 completion gate and exactly one next branch

Leave the six-hour observation 02 and target untouched until collection and
final snapshots finish (recorded expected finish approximately 2026-09-08
14:27 UTC). An exited systemd unit is not sufficient evidence of completion.

1. Discover the bridge with the configured ssh-mcp connection and read-only
   identity/network/UART/TFTP checks. Verify the observer and both clients have
   stopped naturally; do not stop/restart them to make this checklist proceed.
2. Preserve the entire original run in a distinct immutable private archive,
   including source snapshots, client results, all frame logs, runtime state,
   stderr, raw anomalies and neighbor metadata. Record every file's SHA-256.
3. Verify **both** client results, requested/observed duration, continuity,
   frame counts, FPS/motion gates and runtime identities. Independently replay
   direct and HTTPS frame streams on the VM, then correlate shared capture and
   encode timestamps, hashes and exact anomalous bytes. Inspect **every** anomaly
   directory, including previous/next metadata and snapshot failures.
4. Scan credentials using the existing private scanner. Keep any contaminated
   original private and unchanged; preserve sanitization provenance separately.
   Transfer the **complete** archive with authenticated SFTP, verify archive
   size/SHA-256 and all contained file hashes on the VM, and retain replay/audit
   results outside the immutable run. No deployment before these gates finish.

| Branch | Required observation | Next action |
| --- | --- | --- |
| A | Direct and HTTPS anomaly, same capture/encode key and matching raw payload | Fault is below nginx. Deploy the separately built diagnostic capture candidate for observation 03. |
| B | Anomaly only on HTTPS | Leave uStreamer capture unchanged; isolate nginx/HTTP/TLS/client framing. |
| C | Anomaly only on direct | Inspect uStreamer per-client HTTP/fan-out behavior before changing capture. |
| D | No anomaly on either path | Do not infer disappearance or restart qualification. Deploy the separately built non-production diagnostic candidate for observation 03. |

Do not select a branch from partial results, missing-client evidence or mere
elapsed time. Conflicting/unmatched anomalies require resolution before the
branch conditions can be established. Record exactly one supported branch
once the complete archive/replay supports it. No branch has been selected in
this offline preparation.

Observation 03 is root-cause collection until recurrence or a bounded **24-hour
maximum** (longer than the original roughly 15-hour recurrence). Its duration
has zero qualification value. Preserve direct/HTTPS collection and unchanged
video settings, inspect resource/counter coverage, and archive any recurrence.
If the exact tail is already present at DQBUF, archive that proof without
trimming and only then prepare the second Linux uvcvideo diagnostic patch.

That kernel patch should maintain a bounded ring near the affected stream with
UVC header length/flags, PTS/SCR, FID/EOF, URB and packet status/actual length,
destination bytesused before/after copy and the actual selected copy bytes.
Flush on a suspicious completed frame. Include enough packet bytes at the
header/copy boundary to discriminate malformed device framing from a driver
header-handling error; metadata alone cannot prove byte origin. Bound capture
memory, flush volume and suppression counters. Do not implement it before
DQBUF runtime proof, and do not make a production correction in either patch.

Once runtime evidence demonstrates the first faulty layer, propose the smallest
fix there. A new 24-hour M8-F qualification may start from zero only after a
candidate fix, bounded stress, M8-E regressions and zero escaping anomalies.

## Offline validation evidence

The final VM preparation passes **111 repository tests**, including 13 compiled
C diagnostic fixtures and offline correlation/tamper checks. The complete
native uStreamer and dump binaries compile/link from the patched tree (native
smoke build disables the optional process-title feature only). AddressSanitizer
and UndefinedBehaviorSanitizer pass the preserved-payload/burst harness.

`verify-encoder.py` compares the baseline HW encoder to the patched encoder
with diagnostics off/on for eight fixtures: exact EOI, preserved tail, zero tail
and garbage tail, each with/without DHT. All 24 executions retain identical
output bytes within each fixture; the missing-DHT cases exercise the original
insertion path. This is offline semantic evidence, not capture/HTTP HIL or FPS
qualification. Reproduce with new output paths:

```sh
python3 build/ustreamer/diagnostics/verify-encoder.py \
  --baseline /path/to/pinned-source-with-accepted-capture-controls \
  --patched /path/to/prepared-diagnostic-source \
  --output /path/to/new/encoder-comparison
```

The machine-readable preparation record is
[diagnostic-preparation.json](../../../research/evidence/m8f0/diagnostic-preparation.json).
Full native logs, binaries, dependency archives and comparison payloads stay
under ignored `out/m8f0/diag-*`. Failed preliminary native builds are retained
(the initial header-only build lacked the multiarch JPEG include path).
No hardware evidence or target-deployable ARM64 binary is claimed by this record.
