# M8-F0 diagnostic harness revision 2

Branch A and the failed ARM64 preflight are preserved at `ae030e6`.
Four full DQBUF buffers establish the anomaly before uStreamer validation.
Device versus Linux uvcvideo origin remains unproven. The old uStreamer-only
Observation 03 is superseded: a passing hardened preflight gates a separate
Linux diagnostic, not another userspace-only observation.

This revision removes the one-second anomaly admission limiter. Metadata has
an independent 64 MiB conservative output reservation and 8192 events per stage.
Raw files have a separate 64 MiB total allowance and 32 files per stage. Raw
exhaustion records `raw_dump_status=quota_exhausted` and does not affect metadata
admission. Every admitted event retains the full exact tail, hashes, lengths,
timestamps and applicable V4L2 identity. The pending queue has 512 entries and
32 MiB of payload memory; any queue/metadata-capacity loss is explicitly counted
as suppression and fails preflight. No normal full payload is stored.

Output is written privately to `.partial` files and published without replacing
existing records. Partial files, write errors, unmatched counts, metadata loss
or missing V4L2 correlation fail preflight. Previous session directories cannot
be reused. The bounded recent ring still rolls normally; snapshots show only
retained entries and cannot prove an earlier unretained boundary was clean.

The runtime sampler verifies all real/effective/saved/filesystem UIDs and GIDs
in the live uStreamer process, then creates a request as that numeric UID/GID.
It publishes a fresh 32-character random hexadecimal nonce without replacing
an outstanding request. The writer publishes a nonce-correlated recent snapshot
before a nonce-correlated result. The requester requires success within five
seconds. Invalid ownership, no writer, a full snapshot allowance, a partial
snapshot or missing acknowledgement is a diagnostic failure. Preflight requests
three snapshots and reconciles every request/result with final summary counters.

Native validation: 113 repository tests pass; the 300-event burst retains all
metadata and 96 raw payloads; sanitizers pass; 24 HW encoder comparisons remain
byte-identical. ARM64 preflight passed independent VM review: 21/21 anomaly metadata records
and full payloads, zero suppression, three acknowledgements, exact mode and
video/HID/MSD/resource gates. Nothing in this revision changes
production capture, JPEG validation, frame bytes or qualification policy.
