# M8-F1 authorized diagnostic kernel

The user explicitly authorized a diagnostic kernel with exact Run 03 userspace, and one preparatory kvmd restart for a fresh generation. The original missing-interface preflight remains preserved.

Built on the VM from the existing candidate-2 source without source changes, clean builds or production fixes. `PROC_PAGE_MONITOR` and `SLUB_DEBUG` are enabled with selected stack support; `SLUB_DEBUG_ON` remains disabled. The exact configuration delta and artifact hashes are in `manifest.json`. An incremental rebuild reproduced the Image hash. This is diagnostic evidence, not a new qualification or M8-F acceptance.

The enrolled root archive and DTB are byte-identical to Run 03. RAM boot passed on the bridge. A live audit compared all 10,652 regular `/usr` files with hashes extracted directly from that archive, including cpio hard-link handling: zero mismatches. `/proc/self/smaps_rollup` and `/proc/slabinfo` exist; all inspected runtime slab debug flags are zero. The first full sample captured all required memory fields for seven service processes in 0.521 seconds. Overhead under the two-client workload remains to be checked from the observation.

The observation uses the unchanged authenticated video/browser and HID/MSD workload workers. Its controller records the preparatory restart, starts the 12-hour clock after both clients are active, prohibits main-generation changes during observation, and schedules exactly one kvmd restart at the end followed by 15 minutes of recovery sampling. No nginx restart, HDMI interruption, cache dropping, production Python instrumentation, or additional qualification is scheduled.

Because the diagnostic kernel differs, any supplemental interpretation of Run 03 must explicitly account for that difference in an independent review. No automatic acceptance, A/B/C/D memory outcome, release tag or P1 work is authorized by this build.
