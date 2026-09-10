# Run 03 independent acceptance review — outcome B

**MEMORY REVIEW INCONCLUSIVE. M8-F remains OPEN.** Run 03 remains completed functional soak evidence, not an accepted M8-F baseline. Run 02 remains permanently **FAILED**. P1 stays gated; M6/ATX stays **DEFERRED**. No target commands, changes, reboots, new soak, image production, release tag or push were performed for this review.

## Evidence and method

The Build VM rehashed all **12,320 original archived files** and the **150,930,034-byte** private archive (`9e372330f715972b641f177ae5f616d797113580b61a426deea50767ded1d526`). All hashes match. An unchanged independent verifier replay is byte-identical to the existing replay and passes **all 27 automated gates**. The unchanged strict parser accepted **2,583,555 frames**; minimum evaluated throughput remains **29.641667 fps**. This does not override independent journal or memory findings.

All **1,441 resource samples** are reviewed, including the five planned-window samples excluded by the original verifier. Grouping is exactly **comm + PID + start_ticks**. There are 17 observed identities: 16 ordinary service identities and one startup `kvmd` name that becomes `kvmd/main: /usr` with the same PID/start_ticks. That name change is not another restart, and its sample is not merged into the requested exact-comm group.

RSS units below are MiB for readability, not an acceptance threshold. Beginning/final medians use the existing verifier convention: the first/last `min(15, max(1, n//4))` samples of each group. Hourly bins start at qualification start and retain partial-bin counts. Halves split elapsed covered time; final-six-hour statistics apply only with at least six hours of coverage. Exact UTC and both monotonic sample times, every hourly RSS median, half/six-hour statistics and all FD statistics are in [resource-review.json](resource-review.json). RSS shares mappings across processes and must not be summed as private physical memory.

## Every process generation

Intervals are sampled hours since run start, not asserted process birth/death times. FD values are `min–max; beginning→final median`. The complete exact identity is in the first column.

| comm / PID / start_ticks | First–last hour | Samples | RSS min–max | RSS beginning→final (delta) | FD | Unchanged RSS tail (h) |
| --- | ---: | ---: | ---: | ---: | --- | ---: |
| `kvmd/main: /usr` / 3689 / 56801 | 0.000–7.984 | 480 | 58.109–74.859 | 58.734→74.609 (15.875) | 28–29; 29→29 | 0.083 |
| `kvmd/hid-keyboa` / 3694 / 57126 | 0.000–7.984 | 480 | 43.453–43.453 | 43.453→43.453 (0.000) | 22–23; 22→22 | 7.983 |
| `kvmd/hid-mouse:` / 3695 / 57127 | 0.000–7.984 | 480 | 43.863–43.863 | 43.863→43.863 (0.000) | 24–25; 24→24 | 7.983 |
| `kvmd/hid-mouse:` / 3696 / 57128 | 0.000–7.984 | 480 | 43.863–43.863 | 43.863→43.863 (0.000) | 26–27; 26→26 | 7.983 |
| `ustreamer` / 3699 / 57137 | 0.000–7.984 | 480 | 29.711–29.836 | 29.711→29.836 (0.125) | 11–12; 12→12 | 7.017 |
| `nginx` / 3742 / 57655 | 0.000–3.984 | 240 | 9.465–9.465 | 9.465→9.465 (0.000) | 8–8; 8→8 | 3.983 |
| `nginx` / 3743 / 57669 | 0.000–3.984 | 240 | 9.043–9.043 | 9.043→9.043 (0.000) | 16–16; 16→16 | 3.983 |
| `nginx` / 13028 / 1527542 | 4.001–19.984 | 960 | 9.484–9.484 | 9.484→9.484 (0.000) | 8–8; 8→8 | 15.982 |
| `nginx` / 13030 / 1527556 | 4.001–19.984 | 960 | 9.250–9.250 | 9.250→9.250 (0.000) | 15–21; 16→16 | 15.982 |
| `kvmd` / 21814 / 2967474 | 8.001–8.001 | 1 | 19.152–19.152 | 19.152→19.152 (0.000) | 3–3; 3→3 | 0.000 |
| `kvmd/main: /usr` / 21814 / 2967474 | 8.017–24.006 | 960 | 57.539–84.414 | 58.164→84.414 (26.250) | 28–30; 29→29 | 3.405 |
| `kvmd/hid-keyboa` / 21838 / 2967814 | 8.017–24.006 | 960 | 43.570–43.570 | 43.570→43.570 (0.000) | 22–23; 22→22 | 15.989 |
| `kvmd/hid-mouse:` / 21839 / 2967815 | 8.017–24.006 | 960 | 43.680–43.680 | 43.680→43.680 (0.000) | 24–25; 24→24 | 15.989 |
| `kvmd/hid-mouse:` / 21840 / 2967816 | 8.017–24.006 | 960 | 43.805–43.805 | 43.805→43.805 (0.000) | 26–27; 26→26 | 15.989 |
| `ustreamer` / 21843 / 2967825 | 8.017–24.006 | 960 | 29.457–31.957 | 29.457→31.957 (2.500) | 11–12; 12→12 | 8.001 |
| `nginx` / 48241 / 7287395 | 20.001–24.006 | 241 | 9.465–9.465 | 9.465→9.465 (0.000) | 8–8; 8→8 | 4.005 |
| `nginx` / 48243 / 7287409 | 20.001–24.006 | 241 | 8.918–9.168 | 9.168→9.168 (0.000) | 11–17; 16→16 | 3.989 |

Both main kvmd RSS series are monotonically **nondecreasing**, with repeated equal values; neither is strictly increasing at every sample. The first generation has only a five-minute unchanged tail before its scheduled restart. The second has a real **3.405-hour** unchanged tail. All six HID worker generations are RSS-constant, as are the first five nginx identities. The last nginx worker settles after startup. FD excursions occur without retained accumulation; beginning/final medians match for every identity.

### Main kvmd generations and delayed growth

| Run-hour interval | First generation hourly RSS median | Post-8-hour generation hourly RSS median |
| --- | ---: | ---: |
| 0–1 | 59.984 | — |
| 1–2 | 60.109 | — |
| 2–3 | 60.109 | — |
| 3–4 | 60.359 | — |
| 4–5 | 63.609 | — |
| 5–6 | 66.859 | — |
| 6–7 | 70.234 | — |
| 7–8 | 73.484 | — |
| 8–9 | — | 59.539 |
| 9–10 | — | 60.039 |
| 10–11 | — | 60.039 |
| 11–12 | — | 60.289 |
| 12–13 | — | 63.414 |
| 13–14 | — | 66.914 |
| 14–15 | — | 70.414 |
| 15–16 | — | 73.664 |
| 16–17 | — | 76.664 |
| 17–18 | — | 80.414 |
| 18–19 | — | 83.539 |
| 19–20 | — | 84.289 |
| 20–21 | — | 84.289 |
| 21–22 | — | 84.414 |
| 22–23 | — | 84.414 |
| 23–24 | — | 84.414 |
| 24–25 (partial) | — | 84.414 |

The first generation covers **7.983 hours**, cycles 0–89. Its first-half median is **60.109 MiB**, second-half median **68.484 MiB**. RSS grows **13.000 MiB within the second half** and **14.750 MiB over its final six hours**. The early plateau near 60.109 MiB does not persist: growth begins around process age three hours and continues to the restart. Restart release is not evidence against a within-generation leak.

The post-8-hour generation is reviewed independently over **15.989 hours**. Its first-half median is **62.039 MiB**, second-half median **84.289 MiB**. RSS grows **18.000 MiB within the first half**, **8.875 MiB within the second half**, and **2.250 MiB over the final six hours**. The last three full hourly medians are all **84.414 MiB**, with no RSS changes during the final 3.405 hours despite continued exercises. This supports a late observed plateau, but does not explain the earlier delayed growth or establish an allocation/retention bound.

### Workload correlation

Each sample has the nearest HID/MSD cycle, exact recorded lifecycle window, video-client count, login activity since the preceding sample and each separate generation RSS/FD in [resource-correlations.jsonl](resource-correlations.jsonl). Full authentication counts/timestamps are in the resource record.

- The same workload repeats across both generations. Growth starts after an early quiet period in both; the 4-hour nginx restart happens during the first ramp. The 12-hour logout occurs during the later ramp; it does not end that ramp. Temporal association does not identify the allocator or a leak.
- The complete target journal records **1,098 successful logins**, all `expire=INF`. The first generation reaches **372 retained sessions**. The scheduled kvmd restart resets session state; the 12-hour logout explicitly closes **182 sessions**. Subsequent login activity continues to **544 sessions** by the end, including the RSS-flat tail. The harness logs in four times per HID/MSD cycle and deliberately uses `--keep-session` so it does not revoke the video clients. Session count is not FD/socket count. Retained auth objects are a concrete confounder, not proof that they account for the approximately 27 MiB later RSS increase.
- uStreamer generation 21843 grows by **2.500 MiB** at the HDMI-loss/restoration exercise, then stays unchanged for **8.001 hours**. It keeps the same identity; no uStreamer restart occurs at HDMI restoration. This is an observed stable post-event working set, while its precise allocation type is not sampled. The earlier streamer grows only 0.125 MiB and is unchanged for its final 7.017 hours.
- Exactly two video clients are present in every steady sample; transient lifecycle counts and temporary socket unavailability are retained in the record. HID worker RSS is constant in both generations. No evidence shows continuing FD, socket or process accumulation.

## System memory and network

| Metric | Beginning median | Final median | Delta |
| --- | ---: | ---: | ---: |
| MemAvailable (MiB) | 469.355 | 377.828 | -91.527 |
| MemFree (MiB) | 470.750 | 379.066 | -91.684 |
| Cached (MiB) | 345.840 | 397.172 | 51.332 |
| Shmem (MiB) | 345.840 | 397.172 | 51.332 |
| AnonPages (MiB) | 109.961 | 149.168 | 39.207 |
| Slab (MiB) | 29.535 | 30.234 | 0.699 |
| SReclaimable (MiB) | 8.461 | 8.746 | 0.285 |
| process_count | 98 | 98 | 0 |
| socket_count | 98 | 98 | 0 |
| file_nr_allocated | 766 | 773 | 7 |
| sockstat_sockets_used | 112 | 112 | 0 |
| sockstat_TCP_alloc | 8 | 8 | 0 |

MemAvailable loses **91.527 MiB** between endpoint medians. The broad change is largely accounted for by **51.332 MiB Cached/Shmem**, **39.207 MiB AnonPages** and **0.699 MiB Slab** increases; these are accounting categories, not an identified benign owner. `Cached` equals `Shmem` throughout, so this is RAM-backed storage, not evidence of readily reclaimable disk page cache. The archive does not contain interval filesystem allocation, journal-file size/rotation, PSS/private-dirty, heap or allocator measurements sufficient to attribute the growth. A journald/log-file explanation is plausible but **unproven**.

The final-six-hour endpoint loss in MemAvailable is **6.102 MiB**. That includes **2.227 MiB** additional Shmem and **2.145 MiB** AnonPages. Final full-hour MemAvailable medians are **378.135, 377.459, 377.229 MiB**, while main kvmd RSS is flat. This is much slower than the earlier loss and not evidence of a demonstrated runaway leak, but a bounded system-memory plateau cannot be claimed from the process RSS plateau alone. Partial final-bin and transient lows remain visible in the record.

Process count is **95–103** (endpoint medians 98→98); recorded TCP/UDP/Unix socket count **90–103** (98→98); full sockstat sockets **104–117** (112→112). Allocated file handles are **643–823** across lifecycle transitions, settling at approximately **773–774**; beginning/final medians are 766→773. Its final-six-hour endpoint delta is **−1**, not accumulation. `file-nr` unused stays zero and the limit is unchanged. Slab and SReclaimable also level off late.

All eth0 error, drop, collision, FIFO and carrier-error deltas are **zero**. The link transmits **227,275,544,140 bytes**. TCP records **101 retransmitted segments / 160,307,810 outgoing segments**, **615 established resets**, and **149 outgoing RSTs** amid 19,532 passive opens and frequent client/SSH lifecycles. Cumulative protocol-event counts are not retained sockets. TCP timeout, abort-on-timeout, abort-on-memory, memory-pressure, listen-drop/overflow and IP/UDP error counters do not rise. Loss probes/DSACKs occur without failed continuity or throughput gates. No packet capture attributes every RST, so the review does not pretend that every reset was scheduled; the evidence does establish stable connection counts and no unexplained network outage.

## Complete journal review

All **2,080 lines** of `host-kernel-live.log` and **138,701 lines** of `target-journal-live.log` are read and classified. The host file is the complete kernel follow journal captured by the controller; a host all-unit userspace journal was not captured and is not claimed. Full per-class line coverage is in [journal-full-coverage.json](journal-full-coverage.json). Every existing verifier candidate retains its exact original line, source, monotonic timestamp, nearest lifecycle event, nearest cycle, classification and supporting evidence in [journal-candidates.jsonl](journal-candidates.jsonl). Target/bridge clocks are mapped from paired samples with interpolation; receipt latency is unmeasured, so converted timestamps are estimates. Exact target ordering and exact bridge cycle windows provide separate mechanism checks.

| Candidate classification | Lines | Evidence |
| --- | ---: | --- |
| Expected MSD eject/reattach consequence | 544 | Two candidate lines within each of 272 complete five-line READ(10) blocks; DID_OK/DRIVER_OK, Not Ready / Medium not present; archived empty LUN, intentional one-sector read, then three matching full-image direct reads within the same cycle. |
| Expected HID reset exercise | 816 | Three successful `/hid/reset` calls per cycle; exact host evdev checks and released-state cleanup pass. |
| Expected authentication negative test | 272 | Invalid-m8d login denied with 403; each cycle subsequently passes all six evdev checks. |
| Expected disabled-route negative test | 272 | `/msd/reset` deliberately returns 404; it does not issue a SCSI reset. |
| Known documented benign diagnostic | 1 | `Installing SIGUSR2 streamer handler` contains the lexical substring `stall`; normal scheduled kvmd startup and recovered streamer prove its mechanism. |
| Unexplained | **0** | No remaining candidate. |

The full-line review additionally checks successful and denied HTTP statuses, login/session state, clean service transitions, SSH/inventory activity, background service completion, bridge Wi-Fi roaming and five bridge perf self-throttling messages. The target’s password-age diagnostic is consistent with its July RAM clock and September-built image; all 2,263 public-key SSH sessions open and close successfully. Wi-Fi roaming is on the bridge’s unrelated wireless interface, while KVM traffic uses the dedicated wired link; it causes no KVM evidence gap. None of these statements exempts an unrelated meaningful fault.

### Exact scheduled windows and bounded recovery

| Event | Bridge monotonic start→deadline | Action duration (s) | Changed authenticated browser recovery (s from start) | Strict next 120 s fps |
| --- | --- | ---: | ---: | ---: |
| 4h nginx | 15651.425537→15711.425538 | 2.825 | 6.544 | 29.841667 |
| 8h kvmd | 30051.514984→30111.514984 | 2.473 | 20.888 | 29.833333 |
| 12h logout | 44451.456232→44511.456233 | 2.205 | 4.200 | 29.850000 |
| 16h hdmi | 58851.435664→58911.435665 | 15.441 | 16.753 | 29.800000 |
| 20h nginx | 73251.503781→73311.503781 | 2.827 | 6.915 | 29.858333 |

At 8h the old kvmd performs orderly cleanup: all three HID child exit codes and streamer return code are **0**. The API listener is temporarily unavailable; the new generation registers its socket and starts exactly one streamer. All **nine new nginx error-log lines** are refused/missing API-socket connections during that exact restart. The browser and strict client recover before the original deadline; the error mechanism is confirmed, not inferred solely from timing. The entire older nginx-error prefix is byte-identical to the baseline and remains preserved as pre-run history.

At 4h and 20h, nginx stops successfully, validates configuration, starts and accepts replacement clients. At 12h, explicit logout/403/re-login is captured by the real browser. At 16h, archived DRM state confirms DPMS 3 and the controller’s 10-second hold, followed by source restoration, changing browser hashes and a passing strict recovery window. Every MSD cycle’s post-attach hashes and recovery timing are retained in [cycle-correlation.json](cycle-correlation.json); exact service/client sequences are in [lifecycle-correlation.json](lifecycle-correlation.json).

Full-journal searches find **no USB reset, UVC error, failed URB resubmission, MUSB/UDC timeout or stall, SCSI timeout/reset, HID backend/write error, kvmd traceback, unexpected service exit, nginx fatal error, kernel WARNING/Oops/BUG, OOM or unexplained wired-network loss**. The full target dmesg is byte-identical before/after the soak. No Run-02 malformed-JPEG signature, invalid-frame file or strict parser failure recurs. The nine explained nginx upstream errors are retained separately, not hidden by the zero fatal-error result.

## Decision and targeted next step

**Outcome B — MEMORY REVIEW INCONCLUSIVE.** Functional and journal evidence passes. The first long kvmd generation continues growing to its restart, and the later plateau does not concretely explain the repeated delayed growth or prove the system-memory working set bounded. The archive supports neither unconditional acceptance nor a demonstrated continuing leak. No post-hoc MiB threshold, aggregate-across-restarts statistic, restart release or tolerance of malformed JPEGs is used to decide the result.

Proposed targeted diagnostic, **not executed or authorized here**:

1. Reproduce the pinned kvmd/Python 3.14 request and authentication workload in an isolated Build-VM process with `tracemalloc`, allocation-stack diffs, GC statistics and explicit retained-session counts. Use equal workload batches and record exact process generations. Compare the current four-logins-per-cycle pattern with a fixed reusable session set; test session revocation only in this isolated instance so it cannot disturb the live video clients. Measure retained objects/bytes before and after equal batches and after an idle phase. This can test whether auth retention accounts for growth without claiming it explains hardware-process RSS in advance.
2. For a separately authorized target diagnostic, collect `smaps_rollup`/per-mapping private dirty and PSS, RSS/FD, session counts, `/proc/meminfo`, complete filesystem/mount inventories and allocated sizes of RAM-backed files, including journal/nginx logs. Capture journal rotation/retention settings and file replacement. Keep diagnostic evidence off the target RAM filesystem. Preserve PID/start_ticks and the same client/workload counts. Do not attach a profiler, force GC, log out shared sessions or restart the live target merely to obtain acceptance.
3. Correlate equal workload batches and idle periods with attributable live allocations, allocator-retained pages and actual RAM-backed file growth. A finite session/working-set bound or observed allocation reuse must explain the late plateau and the early delayed ramp; stable RSS alone is insufficient if retained objects or files keep accumulating. If a defect is demonstrated, isolate/fix it in a separate authorized slice and require a fresh full 24-hour qualification. Do not rerun the full soak yet.

P1 remains blocked. No baseline tag, acceptance commit or push is made for outcome B. M6/ATX remains deferred; no full-M8 completion is claimed.

## Reproduction

From the repository root, with the original private archive extracted at its recorded location:

```sh
python3 lab/verify-core-soak.py --root out/m8f0/soak03-review/original --output out/m8f0/soak03-review/independent-replay.json
python3 research/evidence/m8f0/soak03/acceptance-review/run03_journal_review.py
```

The review scripts only read the immutable run and write separate derived records. [final-review.json](final-review.json) records the decision; [integrity-review.json](integrity-review.json) records original-file and replay checks.
