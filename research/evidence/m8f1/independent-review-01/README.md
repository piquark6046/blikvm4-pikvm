# M8-F1 observation 01 — independent memory review

**Outcome C — NON-KVMD SYSTEM GROWTH. M8-F OPEN; P1 GATED.**

Reviewed on 2026-09-11 on the Build VM, without contacting the target or bridge, changing runtime state, or starting another soak. Run 03 remains the completed production-candidate 24-hour run pending acceptance; this review does not accept it. Run 02 remains permanently **FAILED**. M6/ATX remains **DEFERRED**. No release tag, acceptance record, P1 work or full-M8 claim is warranted.

Main kvmd reaches an observed terminal plateau, but system memory continues declining because RAM-backed log storage grows. This is not evidence of a continuing main-kvmd private-memory leak at the end of this observation. It is also not a demonstrated bound on the system working set. The previous [Outcome-B review](../../m8f0/soak03/acceptance-review/README.md) is preserved unchanged; its unresolved acceptance blocker is **not superseded as resolved**.

## Evidence and independent method

The authoritative measurement input is the preserved `out/m8f1/review/original/observation01` archive. Neither `analysis.json` nor the downloaded/generated `independent-memory-analysis.json` was used for a conclusion. [recompute.py](recompute.py) independently parses raw `/proc/PID/status`, `smaps_rollup`, `stat`, `meminfo`, `slabinfo` and `file-nr`. It does not import either existing analyzer. [check-context.py](check-context.py) independently verifies provenance, workload records and Run 03 raw time series. The output is [measurements.json](measurements.json), [context-checks.json](context-checks.json), complete readable [tables](tables.md), and sample-level [CSV](series.csv). [memory.svg](memory.svg) and [memory.png](memory.png) are generated from that CSV with matplotlib; the rendered plot was inspected.

All memory quantities in the tables below are MiB (1024² bytes), a presentation unit, **not a newly invented threshold**. Machine-readable memory values are KiB. Counts retain their own units. Hourly bins and named windows are half-open elapsed-time intervals using bridge monotonic receipt times. Full-generation summaries include all 721 old-generation samples, including the last sample at 12 h + 1.71 s. Twelve hourly bins contain 720 samples. The requested hours 2–4 and 4–8 use elapsed [2,4) and [4,8); the alternate ordinal-hours-2-through-4 interpretation [1,4) is also tabulated.

Window endpoint medians use the first/last 15 minutes within the window; min/max use all its samples. OLS slopes describe shape, not acceptance, with no independent-sample p-values or false confidence intervals for autocorrelated minute samples. The quarter-hour medians, terminal constant-run lengths, redistribution between shared/private classes, resource counts and system attribution accompany the slopes. A terminal plateau observed for 75 minutes cannot prove a permanent allocator bound, particularly after an earlier temporary plateau.

## 1. Integrity and scope

- The 88,843,173-byte private archive hashes to `1cbe958805a2a10763143be662ef0988486d4867e488cd8a3a032a3cd553957b`. All **6,393** indexed files were independently rehashed and size-checked, and their actual tar-member bytes matched. The original archive, index and generated descriptions remain unchanged.
- Observation start: **2026-09-10 07:46:24.248 UTC**, bridge monotonic `106139.257735474`. All **721 pre-restart samples** retain `comm=kvmd/main: /usr`, **PID 889**, **start_ticks 22446**. PID and start_ticks are also independently checked against raw status/stat. One boot ID persists in all **737** samples.
- Last old-generation sample: 43,201.711 seconds after observation start. Exactly one scheduled end restart starts at **43,226.807 seconds** and finishes its command in **2.328 seconds**. The preceding collection/inventory accounts for the 26.8-second scheduling offset. The lifecycle record, command output, target journal and observed generations agree. The separately authorized preparatory restart preceded the observation and is not counted as an in-observation restart.
- There are **16** post-restart samples spanning **873.708 seconds (14.562 minutes)**. Excluding the fixed 60-second recovery allowance, 14 stable samples span **782.580 seconds (13.043 minutes)**. The first transient sample has kvmd's new PID but not the completed service cohort. The next two-client sample is still inside the recovery allowance; it is excluded from the stable-window comparison.
- **139 HID/MSD cycles** have passing HID results, attached/ejected/reattached API and target states, read-only backing identity, and the expected MEDIUM NOT PRESENT response while ejected. **837** full 8 MiB direct reads (three initial plus six per cycle) match the frozen G4 hash. This is evidence of retained workload, not a new functional qualification.
- **736/737** resource snapshots show exactly two video clients. The single unavailable state is the scheduled restart transient. Every steady snapshot retains both clients. Of 43,263 browser samples, all **43,217 steady samples** retain connected state, 1920×1080 dimensions and HTTP 200; 43,064 distinct rendered hashes are recorded. The two original workload workers remain present through the observation, with the planned restart interruption retained.
- **Zero** samples report failed systemd units or a failed unit-listing command. Sampler duration is **0.490 seconds median**, **0.525 seconds maximum**. Minute-level snapshots do not prove the absence of arbitrarily short unsampled events.
- All four diagnostic boot artifacts were rehashed. The enrolled root archive (`dadf5f2839f42ae062f793a58a79afb5b2305f01e345a4c2434adbaca29467cb`) and DTB (`3dadd0efd2c9ded33d852446a32e9cd2de2a6989c1f01798c1ab3c6f49887ee2`) are byte-identical to Run 03. uStreamer executable identity and eight frozen effective configuration/unit records match Run 03 and both observation endpoint inventories. Browser/video/HID/MSD worker source bytes match Run 03.
- The preserved pre-observation runtime-audit receipt records **10,652 `/usr` files, zero mismatches**, available memory interfaces and all inspected slab debug flags zero. Its hash is in `context-checks.json`. This receipt is supplementary local preflight evidence, not a second independent per-file runtime measurement; the review independently verifies the root archive and effective contract bytes. There is no new live audit.

The diagnostic kernel differs from Run 03 **only as documented in the authorized build record**: unchanged candidate-2 source and UVC behavior, diagnostic Image and configuration, identical DTB and userspace. Independent parsing of the two complete local archived configs finds exactly the documented delta: LOCALVERSION, PROC_PAGE_MONITOR n→y, SLUB_DEBUG n→y, STACKTRACE n→y, selected STACKDEPOT=y/MAX_FRAMES=64, and SLUB_DEBUG_ON remaining disabled. Diagnostic Image SHA-256 is `700f8c72913ba0b375349b3a8fbc0d1d1c6dbe47752738a6cd66db8a82ec9ab0`; config SHA-256 is `5dc4135a765fb47c9b8d75b074bb7a095e624a9a777ed0836aba0be3ec4d4b16`. Source equivalence relies on preserved build provenance, not a newly reproduced kernel build. This diagnostic observation contributes **ZERO QUALIFICATION DURATION**.

## 2. Main generation and other processes

Selected main-process hourly medians (every requested field, including zero Swap, is in [tables.md](tables.md)):

| Elapsed hour | VmRSS | Pss | Pss_Anon | Private_Dirty | Anonymous |
| --- | ---: | ---: | ---: | ---: | ---: |
| 0–1 | 60.148 | 30.580 | 22.333 | 22.293 | 41.121 |
| 1–2 | 60.273 | 30.845 | 22.598 | 22.605 | 41.246 |
| 2–3 | 60.273 | 31.234 | 22.987 | 23.125 | 41.246 |
| 3–4 | 60.988 | 40.110 | 31.862 | 34.727 | 41.961 |
| 4–5 | 64.262 | 43.387 | 35.139 | 38.004 | 45.234 |
| 5–6 | 67.492 | 46.617 | 38.369 | 41.234 | 48.465 |
| 6–7 | 71.047 | 50.172 | 41.924 | 44.789 | 52.020 |
| 7–8 | 74.289 | 53.417 | 45.169 | 48.035 | 55.262 |
| 8–9 | 77.477 | 56.607 | 48.359 | 51.227 | 58.449 |
| 9–10 | 80.984 | 60.127 | 51.879 | 54.750 | 61.957 |
| 10–11 | 84.328 | 63.471 | 55.223 | 58.094 | 65.301 |
| 11–12 | 84.500 | 63.646 | 55.397 | 58.270 | 65.473 |

| Window / metric | First 15m median | Last 15m median | Min | Max | Descriptive MiB/h |
| --- | ---: | ---: | ---: | ---: | ---: |
| Final 4h Pss_Anon | 47.168 | 55.397 | 46.883 | 55.397 | 2.372 |
| Final 4h Private_Dirty | 50.035 | 58.270 | 49.750 | 58.270 | 2.373 |
| Final 4h Anonymous | 57.258 | 65.473 | 56.973 | 65.473 | 2.369 |
| Final 2h Pss_Anon | 54.033 | 55.397 | 53.484 | 55.397 | 0.669 |
| Final 2h Private_Dirty | 56.904 | 58.270 | 56.355 | 58.270 | 0.669 |
| Final 2h Anonymous | 64.111 | 65.473 | 63.562 | 65.473 | 0.667 |

**Neither the entire final-four-hour nor final-two-hour interval is a plateau.** Accumulation is active in their earlier portions; final-two-hour endpoint Pss_Anon still rises 1.364 MiB. However, Anonymous becomes exactly constant for the last **87 samples / 86.000 minutes**, and Pss_Anon and Private_Dirty become exactly constant for the last **76 samples / 75.005 minutes**, beginning at elapsed hour **10.75039**. The final five quarter-hour medians are identical. This supports a real terminal plateau at the measurement resolution, rather than using a small fitted slope to declare a pass. It does not establish a permanent bound or excuse the later system-memory loss.

Earlier main RSS is nearly flat while PSS/private dirty grows and shared dirty decreases. This is consistent with copy-on-write/shared-page redistribution; RSS alone does not measure private retention. Main Anonymous rises 25.586 MiB over first/last-15-minute medians, while Pss_Anon rises 34.319 MiB. These are overlapping views, not additive allocations. No Python allocation site or specific object-retention mechanism is proven.

Both nginx generations persist: PID/start_ticks 233/1214 and 234/1230. Their anonymous/PSS/private values are flat before restart. uStreamer 899/22781 changes only about 0.031 MiB of anonymous memory after initial warm-up; it remains flat late. The raw kernel comm for uStreamer is `main`; the archived base sampler explicitly identifies `/usr/bin/ustreamer` by executable and normalizes its label. The review retains that distinction rather than treating this as a PID identity contradiction.

HID children 894/22770, 895/22771 and 896/22772 retain essentially flat Anonymous and Private_Dirty: full-generation endpoint Private_Dirty changes are +0.004, 0.000 and +0.012 MiB. Their Pss_Anon shares increase about 0.97 MiB each as sharing changes; this is not evidence that main growth moved to children's private heaps. Main FD median stays 29 (range 29–30), child medians 22/24/26 (one-FD transients), uStreamer 12 exactly, nginx 8/16 (worker startup maximum 21). Process and socket medians settle at 98 without progressive count growth; file-nr allocated changes 766→772, range 766–773. All per-generation hourly values are retained.

## 3. System attribution

First/last-15-minute medians over the old generation:

| Class | Change MiB | Interpretation |
| --- | ---: | --- |
| MemAvailable | −73.902 | Estimated available memory, not a disjoint allocation category |
| AnonPages | +37.344 | System anonymous growth |
| kvmd + three HID children + uStreamer Pss_Anon | +37.270 | Per-sample sum of proportional anonymous shares; explains nearly all AnonPages growth |
| Shmem | +36.887 | RAM-backed file/storage growth |
| Cached | +36.887 | Equals Shmem in these samples; **not another 36.887 MiB** |
| `/var/log` allocated blocks | +33.309 | Most Shmem growth; overlapping with Shmem |
| `/var/log/journal` | +24.852 | Included in `/var/log` |
| `/var/log/nginx` | +8.457 | Included in `/var/log` |
| Slab | +0.758 | Small secondary kernel growth |
| SReclaimable / SUnreclaim | +0.254 / +0.504 | Components of Slab, not additions to it |
| PageTables / KernelStack | +0.129 / −0.043 | Small secondary changes |

The independently summed **Pss_Anon**, rather than summed RSS or Anonymous, accounts for sharing within the service cohort. Its growth differs from system AnonPages growth by only 0.074 MiB. Main kvmd accounts for most of that anonymous retention; remaining cohort changes include sharing redistribution. Other long-lived process RSS is mostly constant. systemd-journald RSS grows 6.332 MiB and journalctl 4.996 MiB, but only RSS was archived for them: file/shmem mappings may overlap the log storage, so these cannot be added as private allocations.

Shmem minus measured `/var/log` block growth leaves **3.578 MiB** over the full observation not assigned to an individual file. `/run` allocated blocks remain 0.297 MiB, `/dev/shm` and `/tmp` stay zero; filesystem-used counters and overlapping mount views are not summed. The evidence supports mixed service-anonymous and RAM-backed logging growth, not exact byte-for-byte reconciliation of all system memory. MemAvailable also reflects watermarks/reclaimability and transient unmeasured processes, so it is not forced to equal an allocation sum.

Largest growing slab classes by first/last-15-minute medians are radix_tree_node **96 KiB**, kmalloc-512 **72 KiB**, dentry **64 KiB**, sighand_cache **64 KiB**, sock_inode_cache **48 KiB**, kmalloc-rcl-128 **36 KiB**, followed by several **32 KiB** classes. Allocated pages are independently calculated as `num_slabs × pagesperslab × 4096`; active object payload is separately retained. There is no dominant slab runaway in these samples.

The decisive separation occurs during the **terminal 75-minute kvmd plateau**. Between robust first/last-15-minute medians, the entire service cohort Pss_Anon changes **0.000 MiB**, system AnonPages **−0.098 MiB**, but MemAvailable falls **5.848 MiB** and Shmem rises **6.414 MiB**. `/var/log` also rises **exactly 6.414 MiB**: journal +5.688 and nginx +0.727 MiB. Slab changes only +0.020 MiB. The late system decline is therefore primarily **RAM-backed log growth**, with a journal allocation step and continuing nginx accumulation. This is the basis for Outcome C.

## 4. Restart release test

The stable post window begins at the first two-client sample after the fixed event recovery deadline. “Stable” denotes service recovery, not heap equilibrium. The final available comparison uses the last five minutes; an all-stable-post sensitivity window is also tabulated. Windows contain 10, 5, 6 and 5 samples respectively; half-open five-minute intervals can include six samples because actual intervals vary around 60 seconds.

| Metric MiB | Pre 10m | Pre 5m | First stable 5m | Final post 5m | Stable − pre5 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Main Pss | 63.646 | 63.646 | 28.611 | 29.449 | −35.034 |
| Main Pss_Anon | 55.397 | 55.397 | 20.365 | 21.201 | −35.033 |
| Main Private_Dirty | 58.270 | 58.270 | 20.260 | 21.180 | −38.010 |
| Main Anonymous / RssAnon | 65.473 | 65.473 | 39.338 | 39.926 | −26.135 |
| Main VmRSS | 84.500 | 84.500 | 58.363 | 58.953 | −26.137 |
| Service cohort Pss_Anon | 103.294 | 103.294 | 65.048 | 66.091 | −38.246 |
| MemAvailable | 393.791 | 394.000 | 431.320 | 432.656 | +37.320 |
| AnonPages | 147.418 | 147.418 | 109.096 | 110.160 | −38.322 |
| Shmem / Cached | 382.379 | 382.406 | 382.514 | 382.613 | +0.107 |
| Slab | 30.857 | 30.859 | 30.873 | 30.867 | +0.014 |

Old main 889/22446 exits; new main is **39187/4347364**. All three HID workers are replaced, as is uStreamer **899/22781 → 39232/4347720**. uStreamer Pss and anonymous memory decrease about **0.074 MiB**, with FD count restored to 12 and both clients recovered. Nginx retains both generations; worker private/anonymous values increase only about 0.039/0.035 MiB during recovery. FD, socket, process, file-nr, kernel/cache and every process's window medians are in the tables; no sustained count growth is hidden by averaging generations.

The service's **38.246 MiB** proportional-anonymous decrease closely matches the **38.322 MiB** system AnonPages decrease (difference 0.077 MiB). Main's proportional share decreases **35.033 MiB**; the remainder is mostly the replaced HID cohort/sharing, plus uStreamer. Main Private_Dirty's 38.010 MiB decrease is an overlapping classification, not an additional release or proof all released pages belonged exclusively to main. MemAvailable recovery of 37.320 MiB is not equal to a main-RSS release, and none of the 36.9 MiB accumulated Shmem is flushed by restarting kvmd. The final post window confirms persistent release while the new process warms up. Minute sampling cannot measure instantaneous exit-before-replacement deallocation.

Restart recovery supports **releasable userspace retention**, but is insufficient to prove bounded retention: an unbounded leak also disappears on process exit. Here the independent terminal plateau supports short-term main stability, while unreleased log storage prevents acceptance.

## 5. Transfer to Run 03

All **12,320 Run 03 files** and its private archive (`9e372330f715972b641f177ae5f616d797113580b61a426deea50767ded1d526`) were rehashed. The comparison independently reads original `resources.jsonl`, not the earlier descriptive resource review. Both datasets identify complete process generations; they are not pooled across restarts.

Run 03's first main generation 3689/56801 has hourly RSS medians **59.984, 60.109, 60.109, 60.359, 63.609, 66.859, 70.234, 73.484 MiB**, before its eight-hour restart. Its second generation 21814/2967474 repeats the delayed growth: first-generation-age hourly medians near **59.539, 60.039, 60.039, 60.289**, later **76.664, 80.414, 83.539**, then **84.289–84.414 MiB** through the final hours. M8-F1's corresponding `/proc/stat` RSS is separately retained; status RSS can differ slightly because these are non-atomic counters. Its final status RSS is **84.500 MiB**.

This reproduces the broad fresh-generation warm-up, delayed growth, terminal RSS plateau and restart-release pattern with essentially the same eventual RSS. M8-F1 adds the previously unavailable evidence that the terminal plateau includes private and proportional anonymous classes; early RSS flatness did not imply flat private accounting. It supports transferring this **explanation**, not qualification duration or a byte-exact growth curve, to the production kernel.

Both runs retain system decline beyond their RSS plateau. Run 03's final full-hour MemAvailable medians are **378.135, 377.459, 377.229 MiB**, with Shmem **397.553, 398.271, 398.836 MiB**. M8-F1 shows the same direction and independently attributes its terminal loss to logs. Absolute system curves differ with elapsed runtime, log/journal allocation/rotation, scheduled events and the diagnostic kernel. Run 03 lacks corresponding per-directory memory accounting and private/smaps data, so this does not prove every Run 03 change has an identical file-level cause.

The exact authorized configuration delta and userspace equality make M8-F1 useful **supplemental explanation**. It cannot safely resolve the Run 03 acceptance blocker: even the diagnostic run does not demonstrate bounded log storage/system memory. This is not a diagnostic-kernel contradiction requiring Outcome D; the observed late non-kvmd growth directly supports Outcome C.

## 6. Decision and narrow next evidence

**Choose exactly C — NON-KVMD SYSTEM GROWTH.** Main private memory is terminally stable; system memory continues declining with directly matched RAM-backed log growth. Outcome A's bounded-system requirement is unmet. Outcome B would mislabel an observed terminal private plateau as continuing main growth. No Python leak label is applied.

Keep M8-F **OPEN**, Run 03 **pending acceptance**, P1 **GATED**, Run 02 **permanently FAILED**, M6/ATX **DEFERRED**. Preserve the earlier Outcome-B review and this new record without rewriting either. No qualifying 24-hour run is rerun, and no release acceptance/tag is created.

The narrow next investigation is **logging retention**, not tracemalloc: first inspect the frozen image's effective journald storage/size/rotation policy, nginx rotation policy and scheduler offline, together with the already archived journal-size steps. Determine whether finite enforceable limits cover both journald and nginx on this RAM root. The missing evidence is a demonstrated storage bound/rotation behavior and attribution of the small full-run residual Shmem change. If archived/offline policy is insufficient, propose separately authorized, diagnostic-only collection of per-file allocated sizes (including deleted-open files), journal usage and rotation events over the relevant rotation boundary under the unchanged workload. Do not drop caches, truncate logs, change production retention, restart kvmd to hide growth, or start that observation as part of this review. Python allocation tracing is not the narrowest diagnostic for the current blocker.

## Replay and preservation

From repository root, using only existing local archives:

```sh
python3 research/evidence/m8f1/independent-review-01/recompute.py
python3 research/evidence/m8f1/independent-review-01/check-context.py
python3 research/evidence/m8f1/independent-review-01/render-tables.py
python3 research/evidence/m8f1/independent-review-01/verify-accounting.py
MPLCONFIGDIR=/tmp/m8f1-mpl /tmp/m8f1-review-venv/bin/python research/evidence/m8f1/independent-review-01/plot.py
```

The plotting environment is VM-only; the first three scripts use only Python's standard library. Raw archives remain private and outside Git. Only scripts, derived numeric evidence, plots and this review are preserved in the repository. `decision.json` is an independent-review decision **not a final M8-F acceptance record**. Review file hashes are in `SHA256SUMS`.

Validation: all **5,155 raw process records** satisfy the checked RSS/PSS accounting identities; all 737 controller records match their archived command stdout; all Swap values are zero. The only status/smaps RSS difference is the new kvmd startup sample. Twelve independently regrouped hourly Pss_Anon medians agree. The target journal contains the preparatory restart before the observation and exactly one service stop/start within it. **22 local labctl tests pass**; no HIL tests were run.
