# Predeclared M8-F2 logging policy

Candidate values: `Storage=volatile`, `RuntimeMaxUse=16M`, `RuntimeMaxFileSize=4M`, `Compress=yes`. No values will be tuned after observing retention results. `ForwardToSyslog=no` overrides Ubuntu's forwarding drop-in to retain one journal mechanism. Nginx choice A: `access_log off; error_log stderr warn;`. Its foreground systemd service captures stderr in the default journal. Existing empty packaged log files may remain but must have zero allocation growth and no writer. The default inactive nginx configuration is not selected by the service.

The preserved installed-version record identifies systemd 259.5-0ubuntu3.4 in the target, frozen rootfs and Build VM. Semantics were checked against that exact version's locally installed `journald.conf(5)` (hash recorded), rather than inferred from a newer online manual:

- Volatile journals use `/run/log/journal` and do not switch to persistent storage on flush. Existing persistent history is not deleted by this setting; deployment therefore uses a fresh RAM boot with the new rootfs, preserving old diagnostic archives.
- Runtime size suffix M means 1024 squared bytes. RuntimeMaxUse and RuntimeKeepFree both apply; the smaller allowance wins. KeepFree retains its installed default. Only `.journal` and `.journal~` files count toward journal accounting.
- RuntimeMaxFileSize controls rotation granularity. Limits are enforced synchronously on extension; no timer or manual vacuum is required. Only archived files can be deleted; active files can cause a documented overshoot. An overshoot must be explained by individual-file evidence, never silently accepted by raising the quota.
- Volatile storage uses a single system journal rather than per-user split journals. Compress=yes compresses data objects above the default 512-byte threshold; it does not promise to compress every message.
- The policy bounds retained bytes rather than promising a fixed retention time. High volume shortens history. Rate limiting remains enabled at its installed defaults. No new namespace or independent log writer is introduced.

Authentication, firewall, TLS/routing, video, HID, MSD, descriptors and application behavior remain unchanged. Disabling duplicate nginx access files avoids regular-file growth and URL/query retention there; existing kvmd authentication/access auditing remains under the quota. Nginx error diagnostics retain warn and more severe levels. Test payloads contain no credentials. Raw runtime logs remain private.

## Predeclared targeted test

A 2-hour fresh-RAM retention test, zero 24-hour qualification credit, using production candidate-2 Image/config and unchanged DTB. Two authenticated video clients, actual browser UI, native 1920x1080 MJPEG 30 fps, unchanged strict JPEG and >=27 fps window checks, periodic host-verified HID and read-only MSD cycles. No application restart or manual journal rotation/vacuum during the accepted interval.

Minute samples must record journalctl disk usage, actual journal file size/st_blocks/inode identities, oldest/newest retained journal markers, all requested directory allocations, Shmem/MemAvailable, available RSS/PSS, process/FD/socket counts and service health. An explicitly marked harmless elevated journal load and normal SSH/sudo sessions exercise automatic rotation. The fixed load is declared before launch. Preserve the bridge journal stream independently so deletion can be proven against earlier recorded entries.

Acceptance requires automatic removal of old journal files/entries, bounded repeated usage after rotation, stable system-memory working set, healthy journald, no unbounded nginx access writer and all functional regressions passing. There is no invented memory-slope tolerance: inspect the full series and terminal working set. Continuing unexplained decline selects B; a policy regression selects C. Insufficient rotation/plateau evidence is inconclusive, not A.

No P1, release or baseline tag. A fresh full 24-hour run is still required after candidate freeze and review; Run 03 cannot become that qualification retroactively. Run 02 FAILED permanently; M8-F1 supplemental; M8-F OPEN; M6/ATX DEFERRED.

The fixed elevated load is 32 marked, credential-free syslog messages per second, each with a unique 384-hex-character payload. Additionally, ten fresh SSH commands per minute execute `sudo -n true`. This exercises ordinary session/PAM logging independently of synthetic log ingestion. Load parameters are frozen before launch. The load unit is stopped only after final sampling or after a preserved failure.

The first cpio reproducibility attempt failed solely on 55 extraction-time directory mtimes. Both failed cpio outputs are preserved under `out/m8f2/build{1,2}/initramfs-unreproducible-01.cpio.gz`. Applying the baseline builder's SOURCE_DATE_EPOCH normalization made both outputs identical. Independent cpio parsing verifies all 14,596 existing entries retain modes, owners, mtimes and device metadata; only nginx logging bytes change, plus the new journal configuration directory/file. No package changes occur.

Preflight 01 exposed a precedence defect before the retention interval: vendor `syslog.conf` sorts after `60-blikvm-bounded.conf`, overriding the added ForwardToSyslog=no. The first boot/candidate is preserved, not accepted. The final drop-in is named `zz-blikvm-bounded.conf` so its explicit forwarding policy wins; all four predeclared quota/storage/compression values remain unchanged. Both rootfs and initramfs builds are repeated after this filename correction. No manual edits to the running target are used to conceal the packaging error.
