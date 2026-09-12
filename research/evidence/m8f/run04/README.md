# M8-F Run 04 — accepted production core soak

**CORE KVM SOAK PASSED; ATX DEFERRED**

The independent Build VM review accepts the exact production candidate
`8650c6684b5f8bc0e1b0e0c168ddb5902280484c`. It was pushed before rebuilding;
the production Image, accepted DTB, frozen kvmd/uStreamer/HID/MSD stack and
M8-F2 logging policy were hash-verified. No diagnostic kernel, taildiag,
experimental tracing or parser relaxation was used.

The run started September 11 at 08:10:19.482586 UTC and ended September 12
at 08:10:58.787199 UTC: **86,439.305 continuous seconds** including final
checks. All 27 original automated gates pass independent VM replay.
The unchanged strict worker processed 2,583,116 frames, with zero malformed
escaping payloads. Minimum unaffected 120-second delivery was **29.65 fps**;
minimum recovery delivery was **29.8 fps**. Actual Chromium video/auth/motion,
two clients and exact V4L2 MJPEG 1920×1080 30/1 pass. All five scheduled events
recover within their unchanged 60-second windows. Action completion is not
used as a substitute for the separately replayed recovery video gates.

All **272 real host-verified keyboard/absolute/relative/neutral HID and
read-only MSD cycles** pass. All **1,635 O_DIRECT whole-image reads** match
the approved 8 MiB image. No writable transition or unexplained USB reset,
MUSB/SCSI timeout, HID failure, service crash, kernel warning/Oops/BUG or OOM
appears in the reviewed qualification interval.

## Logging and memory review

All **1,443** resource records were independently matched to raw command
stdout. Both effective journald/nginx endpoint configurations are identical.
Runtime journal allocation ranges from 4 to **16 MiB**, never above the
unchanged cap; individual files never exceed 4 MiB. **10 automatic file
removals** demonstrate retention. Sampled totals can remain 16 MiB while old
files are replaced; constant total usage does not imply missing rotation.
`/var/log` stays **4,096 allocated bytes**, persistent journal and nginx log
allocation remain zero, nginx files stay empty, and endpoint audits find no
nginx regular-log writers. No manual vacuum, deletion, truncation, cache drop
or journald restart was used.

The required phase medians, in MiB, retain warm-up, lifecycle events and the
final extra-workload sample:

| Phase | MemAvailable | Shmem | AnonPages | Main kvmd RSS |
| --- | ---: | ---: | ---: | ---: |
| First 2 hours | 470.188 | 337.973 | 116.131 | 61.270 |
| Middle, hours 2–20 | 443.102 | 353.551 | 129.641 | 65.797 |
| Final 4 hours | 421.063 | 353.551 | 149.969 | 84.324 |
| Final 2 hours | 420.840 | 353.551 | 150.023 | 84.324 |

The middle period includes the 8-hour restart and subsequent process warm-up;
its slope alone is not a terminal leak test. Main kvmd RSS reaches 84.324 MiB
and is exactly constant in every final-two-hour sample. Final-four-hour Shmem
ranges only from 353.546875 to 353.5546875 MiB; journal allocation is bounded
through file replacement. MemAvailable hourly medians for hours 20, 21, 22,
and 23 are **421.561, 421.098, 420.818, 420.955 MiB**. This is a stable terminal
range with fluctuations, not the prior continuing logging-driven decline.

The terminal sample after the final extra cycle reports 403.699 MiB
MemAvailable and is retained. Including it yields a final-two-hour OLS slope
of -0.398 MiB/hour; the complete 22–24h interval before that extra endpoint
has +0.0117 MiB/hour. This endpoint-sensitive slope is not treated as a
monotonic leak or hidden by deleting samples. First/last 15-sample medians
are 421.172/421.098 MiB. Small AnonPages (+0.0586 MiB in those medians) and
Slab (+0.0273 MiB) changes are retained, with stable process/socket/file counts;
no new numeric acceptance tolerance was introduced.

At the scheduled kvmd restart, coarse pre/post MemAvailable is
432.703/539.391 MiB and AnonPages is 137.883/56.184 MiB. Main kvmd RSS is
73.020 MiB before restart; the immediate post-restart sample catches the
service between generations with no main process. This measures aggregate
restart release, not private allocation attribution to one process.
Production PSS/smaps interfaces are not required. M8-F1 only supplements the
previous private/anonymous plateau and logging attribution; no unrelated
diagnostic-kernel conclusion is transferred.

## Full journals and provenance

The review processes the complete **139,325-line target journal** and
**77,294-line host journal**, using nearest sampled monotonic clock pairs
rather than the target's different wall clock. All 272 target auth errors
are deliberate invalid-user tests. All 272 SCSI error stanzas are NOT READY /
MEDIUM NOT PRESENT within intentional eject cycles. Ten upstream connection
errors plus normal client shutdown occur inside the scheduled kvmd restart.
Final client teardown is after controller completion. Benign preset/optional
kernel-capability messages are documented boot context. Bridge Wi-Fi roaming,
Internet NTS and background network-wait failures do not interrupt the isolated
Ethernet workload; the unchanged independent video gates pass. Prior host
history is retained, not retroactively accepted. No unexplained persistent
qualification failure remains. The private per-line classification index is
hashed in `acceptance.json`.

The **237,350,349-byte** private archive SHA-256 is
`0119824b08eaa2c939a38df0d6c0a7bdf7d5a5fbea2a10d2a3be616cced0d7f9`.
Authenticated SFTP transfer, archive identity and **all 12,398 file hashes and
sizes** were independently verified. Public evidence contains only summaries,
hashes and review code. Raw journals, enrollment and credentials stay outside
Git. The first launcher failure (missing frozen support files before workload
startup) remains preserved and contributes zero qualification duration.

`acceptance.json` is the final machine-readable decision. `artifact-hashes.json`
is the earlier pre-HIL proof, so its own acceptance field remains false.
`controller-diff.json` records the bridge-only logging/journal/restart-sample
additions; all production and workload/parser workers stay frozen.
For replay, place the private archive as `archive.tar.gz`, receipt as
`receipt.json` and file index as `files.json` beside copies of these review
scripts in a private directory. Run `verify-archive.py`, `resources-review.py`
and `journal-review.py`; run the unchanged candidate `lab/verify-core-soak.py`
against `original/m8f-run04/soak`. The resource script deliberately returns
numeric evidence with review pending: human interpretation above is required.

Run 02 stays **permanently FAILED**. Run 03 stays **completed but unaccepted
historical evidence**. M8-F1 and M8-F2 remain supplemental diagnosis and bounded
logging evidence. P1 is unlocked. M6/ATX and writable MSD remain deferred.
No physical SD write occurred. This is a finite 24-hour qualification;
minute sampling cannot exclude unsampled transient peaks or prove permanent
allocator boundedness.
