# M8-F2 — bounded logging attribution and policy

**Outcome A — LOG GROWTH EXPLAINED AND BOUNDED. M8-F remains OPEN; P1 GATED.**

The two-hour targeted retention test passed on 2026-09-11. This is not a full M8-F qualification and contributes zero qualification duration. Run 02 remains permanently FAILED; Run 03 remains completed functional evidence but unaccepted; M8-F1 remains supplemental; M6/ATX remains DEFERRED. No release or M8-F baseline tag is created. A fresh full 24-hour qualification is still required, and is not started by this checkpoint.

## Diagnostic checkpoint publication

Commit `d51cc3f39e5a60add8cabc55a7fe9bacceea32e5` was pushed to `main` after fetching refs and scanning all 19 outgoing files against the local qualification secret and private-key/session/PAT patterns. No credential matches were found. Its prerequisites were already on origin. No tags were pushed or created.

## Offline attribution

[All 737 raw resource samples](evidence/m8f2/offline-01/README.md) were independently reconstructed and checked against raw command stdout. All 6,393 immutable M8-F1 archive files and tar-member contents were rehashed. No live observation was used for this attribution.

The terminal 6.4140625 MiB `/var/log` increase is exactly **6,725,632 bytes**: **5,963,776 bytes `/var/log/journal` plus 761,856 bytes `/var/log/nginx`**. `/run/log/journal` contributes zero. Neither measured directory alone accounts for the total. This is the original terminal first/last-15-minute median comparison, not a full-observation endpoint delta.

Across all 737 samples, `/var/log` grows from 11,956,224 to 47,292,416 allocated bytes; journal from 11,927,552 to 37,986,304; nginx from 24,576 to 9,302,016. The runtime journal remains zero. Every requested endpoint, hourly median, hourly OLS growth rate, decrease count and raw series is published in the linked report. No measured log directory decreases. Journal allocation has five steps; the archive lacks individual journal identities, so rotation without a net decrease cannot be excluded. No bound was demonstrated in M8-F1.

[Generator and workload attribution](evidence/m8f2/offline-01/interpretation.md) identifies kvmd `aiohttp.access` as the dominant journal generator: 51,998 of 53,307 kvmd messages. The complete embedded nginx endpoint logs add 52,231 requests / 9,296,534 serialized bytes, dominated by browser `/api/msd` polling. Continuous video produces only two completed access entries in this archive. SSH/sudo/PAM diagnostic traffic is a measurable secondary source: sampler-adjacent administrative entries total about 0.82 MB rendered text. Per-cycle API counts and hourly journal/cycle/sample counts establish the periodic HID/MSD component. Rendered text sizes are not compressed journal allocation sizes. Structured systemd unit fields were not archived; exact `_SYSTEMD_UNIT` grouping is unavailable.

## Frozen policy and reproducibility

[Policy rationale and installed systemd semantics](evidence/m8f2/policy-01/README.md) use exact installed systemd **259.5-0ubuntu3.4**, its local manual and effective runtime configuration. The predeclared values remain unchanged:

```ini
[Journal]
Storage=volatile
RuntimeMaxUse=16M
RuntimeMaxFileSize=4M
Compress=yes
ForwardToSyslog=no
```

Nginx choice A disables duplicate access logging and sends warn/error diagnostics to stderr under the same journal quota. Existing packaged empty nginx log files remain empty and have no writer. kvmd's existing authentication/access auditing remains unchanged. The final drop-in sorts after Ubuntu's forwarding drop-in; its effective precedence is tested.

Both public rootfs and initramfs builds reproduce byte-for-byte. The [file diff](evidence/m8f2/policy-01/file-diff.json), [independent cpio comparison](evidence/m8f2/policy-01/cpio-diff.json), [public hashes](evidence/m8f2/policy-01/public-manifest.json) and [runtime contracts](evidence/m8f2/policy-01/runtime-contracts.json) preserve the evidence. All 14,596 existing cpio entries retain modes, owners, mtimes and device metadata. Only nginx logging payload changes; the journal configuration directory/file is added. Package versions and all other file payloads are identical to M8-E. Production candidate-2 Image/config and DTB are unchanged.

The initial cpio timestamp mismatch, forwarding-precedence preflight defect and two bridge launcher setup failures are retained in `out/m8f2` and on the bridge. They preceded the accepted retention interval. No retention values, functional gates or target application code were tuned to obtain a pass.

## Two-hour retention evidence

The measured run starts **03:53:46 UTC** and completes **05:53:57 UTC**, September 11. The scheduled load interval is 7200 seconds; final inventory accounts for the extra 11 seconds. It has 121 raw resource samples, 23 host-verified HID/MSD cycles, 1,200 fresh SSH/sudo administrative sessions, two authenticated video clients, the actual browser UI, and native 1920×1080 MJPEG at 30 fps. There are no application restarts or lifecycle exclusion windows.

The fixed elevated logger emits 32 unique 384-hex-character payloads per second. The bridge captures **230,740 consecutive probes starting at zero**, with no gaps, plus normal administrative/application messages. No manual vacuum or rotation was issued. The logger stops after final sampling; its shutdown is not used as a memory-release test.

[Retention review](evidence/m8f2/retention-01/review.json) and [complete numeric analysis](evidence/m8f2/retention-01/logging-analysis.json) show:

- **89 automatic journal-file removals** between minute samples. The initial marker is present at baseline and absent by **362.095 seconds**. The oldest retained entry advances **7015.799 seconds**.
- Actual journal file allocations exactly equal `/run/log/journal` allocated-byte totals in all 121 samples. `journalctl --disk-usage` succeeds in every sample. Initial usage is 4 MiB; maximum sampled total is **14,114,816 bytes (13.460938 MiB)**, below the fixed 16 MiB policy. Maximum individual allocation is 4 MiB. Later samples remain around 13.45 MiB across five files as old files are removed.
- `/var/log` is **4096 bytes throughout**; `/var/log/journal` and `/var/log/nginx` remain zero allocated bytes. Both nginx files remain empty and have no writer at the effective endpoint audits.
- Journald is healthy in every sample. Its anonymous RSS quarter-hour medians are 1.320–1.332 MiB; mapped journal memory overlaps Shmem and is not added again. No suppressed/dropped-message or unexplained failure candidate appears in the full journal review.
- All **26 functional replay checks pass**. The unchanged strict worker processes **215,655 frames**. All 60 full 120-second windows exceed 27 fps; the minimum is **29.691667 fps**. Browser continuity, authentication, dimensions and changing rendered frames pass. All host evdev comparisons and read-only media hashes pass.

## Memory decision

Quarter-hour medians, in MiB, retain warm-up rather than hiding it:

| Elapsed minutes | MemAvailable | Shmem | AnonPages | Slab |
| --- | ---: | ---: | ---: | ---: |
| 0–15 | 457.590 | 347.430 | 121.516 | 29.691 |
| 15–30 | 453.797 | 347.430 | 122.324 | 29.918 |
| 30–45 | 450.070 | 347.430 | 123.211 | 30.023 |
| 45–60 | 451.305 | 347.434 | 124.043 | 30.105 |
| 60–75 | 453.230 | 347.430 | 124.391 | 30.137 |
| 75–90 | 451.277 | 347.434 | 124.430 | 30.160 |
| 90–105 | 451.359 | 347.434 | 124.398 | 30.164 |
| 105–120 | 452.777 | 347.430 | 124.457 | 30.184 |

Shmem's first/last-15-minute medians are identical. MemAvailable includes initial warm-up and transient administrative/cycle activity; it is not constant sample by sample. The later medians do not continue declining. Main kvmd also warms up: status RSS quarter-hour medians reach about 61.60 MiB in the second hour and remain near that level. Its FD count remains 29; uStreamer stays at 12; nginx master/worker settle at 6/14. Process/socket counts show no progressive growth. Small later anonymous/slab changes are retained in the raw series, not concealed by a new numeric tolerance. PSS is unavailable on the unchanged production kernel and is explicitly recorded unavailable; no diagnostic kernel or Python allocation instrumentation was introduced.

This establishes the targeted logging working-set bound and observed post-warm-up memory stability under the declared load. It does not establish permanent allocator boundedness, substitute for the longer workload or retroactively accept Run 03. Minute samples cannot exclude arbitrarily short unsampled peaks.

The complete 109,238,009-byte target journal and host journal were reviewed. All 23 target authentication errors are intentional invalid-user cases within HID cycles; 92 keyword-matching HTTP records are expected reset API tests. All 23 host SCSI error stanzas have NOT READY / MEDIUM NOT PRESENT and occur during intentional eject cycles. Bridge Wi-Fi roaming messages do not affect the isolated target Ethernet/video path; independent continuity passes. No unexplained candidate remains.

## Preservation and next gate

The private archive is **67,245,743 bytes**, SHA-256 `7e9f0fe786db010dc1c133f36943620b0b19fa8530624600b5f0905e7b7bf72f`. Its archive/index/receipt are mode 0400 and immutable on the bridge. Authenticated SFTP transfer and all **3,619 file hashes/sizes** were independently verified on the VM. Raw evidence and enrollment remain outside Git. Public evidence contains scripts, configuration, numeric summaries and hashes.

Outcome A freezes the logging candidate by the public manifest and source checkpoint. The next full M8-F must start from zero on this candidate, preserve all five lifecycle events, strict JPEG validation, >=27 fps windows, two clients, actual UI, periodic HID/MSD, resource sampling and full journal review. Add explicit logging checks for the configured journal bound, bounded `/var/log`, and no unexplained continuing MemAvailable decline. Do not count this retention test or Run 03 toward that run. Only a fresh 24-hour pass followed by independent review may record **CORE KVM SOAK PASSED; ATX DEFERRED**, create the M8-F baseline tag and unlock P1.

Replay:

```sh
python3 research/evidence/m8f2/offline-01/recompute.py
python3 research/evidence/m8f2/offline-01/correlate.py
python3 lab/verify-logging-retention.py --root out/m8f2/review/original/retention01 --output out/m8f2/review/functional-replay.json
python3 lab/logging-analyze.py out/m8f2/review/original/retention01 research/evidence/m8f2/retention-01
python3 lab/logging-review.py out/m8f2/review/original/retention01 research/evidence/m8f2/retention-01
```
