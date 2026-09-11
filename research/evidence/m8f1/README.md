# M8-F1 Stage 0: Run 03 restart boundary

Outcome-B checkpoint `77d95ce` is present on origin/main; push confirmed up to date. No release tag created.

All input SHA-256 values match immutable Run 03. Windows are half-open and use bridge receipt times. Stable post-restart begins at the first sample after the original recovery deadline with two clients and main kvmd present. This is service recovery, not allocator equilibrium.

| Metric | Pre 30 min | Pre 5 min | Stable post 5 min | Post 30 min |
| --- | ---: | ---: | ---: | ---: |
| kvmd_main_rss_bytes (MiB) | 74.359 | 74.859 | 57.664 | 58.914 |
| ustreamer_rss_bytes (MiB) | 29.836 | 29.836 | 29.457 | 29.457 |
| rss_bytes:nginx:13028:1527542 (MiB) | 9.484 | 9.484 | 9.484 | 9.484 |
| rss_bytes:nginx:13030:1527556 (MiB) | 9.250 | 9.250 | 9.250 | 9.250 |
| MemAvailable_bytes (MiB) | 419.133 | 417.797 | 447.395 | 445.824 |
| MemFree_bytes (MiB) | 420.473 | 419.141 | 448.736 | 447.164 |
| Cached_bytes (MiB) | 368.662 | 368.809 | 368.914 | 369.062 |
| Slab_bytes (MiB) | 29.895 | 29.902 | 29.895 | 29.906 |
| SReclaimable_bytes (MiB) | 8.547 | 8.547 | 8.547 | 8.547 |
| SUnreclaim_bytes (MiB) | 21.348 | 21.355 | 21.348 | 21.359 |
| Shmem_bytes (MiB) | 368.662 | 368.809 | 368.914 | 369.062 |
| AnonPages_bytes (MiB) | 137.184 | 137.898 | 107.316 | 109.066 |
| PageTables_bytes (MiB) | 2.807 | 2.805 | 2.789 | 2.797 |
| KernelStack_bytes (MiB) | 1.875 | 1.867 | 1.906 | 1.906 |
| process_count | 98.000 | 98.000 | 99.000 | 99.000 |
| socket_count | 98.000 | 98.000 | 98.000 | 98.000 |
| file_nr_allocated | 771.000 | 771.000 | 771.000 | 771.000 |
| file_nr_unused | 0.000 | 0.000 | 0.000 | 0.000 |
| file_nr_limit | 9223372036854775808.000 | 9223372036854775808.000 | 9223372036854775808.000 | 9223372036854775808.000 |

Sample counts: 30, 5, 6, 31.

MemAvailable recovered 29.598 MiB between five-minute medians; main kvmd RSS fell 17.195 MiB, AnonPages fell 30.582 MiB, and uStreamer RSS fell 0.379 MiB. Both nginx RSS values were unchanged. Cached/Shmem increased 0.105 MiB. These are overlapping accounting categories; process RSS must not be summed as private physical memory.

Minute-resolution sampling cannot quantify instantaneous release between process exit and replacement startup. The restart also replaces HID children and uStreamer. There is no private/anonymous/PSS or filesystem allocation measurement to attribute the released memory solely to main kvmd or determine a bound. Stage 0 remains inconclusive; proceed with the targeted live observation.

M8-F OPEN; Run 03 completed functional evidence, not failed or accepted; Run 02 permanently FAILED; P1 GATED; M6/ATX DEFERRED.

## Live preflight: required interfaces unavailable

The same Run 03 boot and second main generation (PID 21814, start_ticks 2967474) remain active. All four bridge boot-artifact hashes match Run 03. Runtime package-file equality has not yet been exhaustively rechecked. The 12-hour observation has **not started**; no kvmd restart, reboot, or production runtime change occurred.

The pinned kernel configuration has `CONFIG_PROC_PAGE_MONITOR` and `CONFIG_SLUB_DEBUG` disabled. A root-level target probe confirms both `/proc/self/smaps_rollup` and `/proc/21814/smaps_rollup` are absent, as is `/proc/slabinfo`. `/proc/PID/status` and `/sys/kernel/slab` are available. Status exposes RSS classes but cannot substitute for PSS/private accounting. See `capabilities.json` and `preflight-review.json`.

The first sampler preflight failed at the missing slabinfo file; its per-process collection also encountered missing smaps_rollup. This is a diagnostic prerequisite failure, **not a Run 03 failure**. The draft controller now checks these prerequisites before launching workload. The sampler preserves explicit unavailable fields. Both scripts compile; 22 labctl tests pass, but neither the full controller nor overhead under two-client video has been validated. No A/B/C/D memory outcome is selected.

A diagnostic kernel would violate the currently required exact runtime bytes and requires explicit authorization. Alternatively, the user can authorize reduced evidence on the original kernel. The pending choice must be resolved before the long run; no silent substitution or fourth qualification is scheduled. The existing generation is already aged, so a fresh warm-up observation also requires a preparatory restart decision.

## Authorized diagnostic kernel and live observation

The user subsequently authorized a diagnostic kernel retaining exact Run 03 userspace and one preparatory kvmd restart. This resolves the earlier preflight scope blocker without erasing it. See [diagnostic-kernel/README.md](diagnostic-kernel/README.md) and [observation-start.json](diagnostic-kernel/observation-start.json).

M8-F1 observation 01 started at **2026-09-10 07:46:24 UTC**, main kvmd PID 889/start_ticks 22446. The first cycle passed; all four initial samples retain two clients and no failed units. The first complete 120-second video window is 29.8083 fps with 3,572 different hashes. Samples take 0.497–0.514 seconds, with maximum initial interval 60.116 seconds. This is startup evidence only, not a memory boundedness result.

The planned single end restart is around **19:46:24 UTC**, with recovery sampling through approximately **20:01:24 UTC**. A bridge finalizer will produce descriptive analysis and a private hash-indexed archive. A VM collection service will transfer and verify that archive and independently regenerate the memory analysis. An independent decision remains required afterward; all acceptance gates remain unchanged.

## Independent completion review — September 11

[Observation 01 review](independent-review-01/README.md) independently rehashes
the completed archive and recomputes raw memory samples. **Outcome C —
NON-KVMD SYSTEM GROWTH**: main private memory is terminally stable, but
RAM-backed logs continue consuming system memory. M8-F remains OPEN; Run 03
is not accepted; P1 remains GATED. Run 02 remains permanently FAILED and
M6/ATX DEFERRED. The diagnostic observation contributes zero qualification
duration. Earlier reviews and this observation archive remain unchanged.
