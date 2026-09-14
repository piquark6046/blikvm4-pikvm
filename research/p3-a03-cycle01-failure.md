# P3-A attempt 03 — stopped at independent cycle-1 journal replay

**Attempt 03 FAILED, 0/12 accepted cycles.** One real reboot and three Chromium
launches occurred. The controller completed; independent acceptance failed.
No retry, later cycle, threshold change, target repair, reboot after failure,
reflash, H5R2 rerun or P3-B/C action followed. P2 remains PASSED, H5R2 ACCEPTED,
P3 UNACCEPTED; M6/ATX and RO/overlay remain DEFERRED.

## Controller R1 verification and source

[Controller R1](p3-controller-r1.md) passed the complete publication lifecycle
on VM and bridge fixtures, including the pinned old-controller failure, with
independent archive replay. The exclusive publisher was unchanged. Local tests
passed before deployment, public files were scanned, and clean commit
`575aab262bd5b48b0527a5f65a112b9e31e43aa9` was pushed and verified on origin/main.
The bridge installed and verified exactly those committed source bytes.
The live controller SHA-256 equals the final bridge-rehearsed source:
`24233b1d50dd05a51bbaefa04b1077f7cc8275eea3b4ad63a068e56b8cf3995a`.

Fresh prestart inventory passed exact accepted H5R2 runtime/input manifests,
physical accepted P2 SD identity, machine/SSH identity, all 10,690 hashes,
healthy filesystem/services and attached RO G4 media/API/whole-host-image hash.
All 2,556 prestart journal records were inspected for errors; the six retained
application errors matched accepted H5R2 records exactly. No state normalization.

## Live cycle outcome

Cycle 1 kept Ethernet connected throughout. It requested exactly one clean
reboot from `1c8365c7-90bf-46fb-8db4-5ec06a745a6a` to
`755c9d0a-65ed-4b20-9b95-3692281e53bb`. Enrolled SSH/trusted HTTPS recovered
in 20.480661619 seconds, within the frozen 180-second deadline. Continuous
passive UART retained the complete SPL/BL31/U-Boot/SD-script/kernel/systemd
chain. Postboot inventories passed the physical RW SD, identities, all hashes,
exact MJPEG 1920x1080 30/1, services, bounded logging and attached RO MSD gates.

The unchanged H5R2 MSD browser protocol completed two launches, then the HID
protocol completed its third launch. The controller reported both protocols
passed, retained its final attached-MSD/identity checks, found no browser UID
processes, archived/sealed the leaf, and exited successfully. Each immutable
checkpoint was published without the attempt-02 duplicate-publication error.
`cycle-final.json` and `result.json` remain provisional, exactly as published;
neither grants acceptance credit.

## Exact independent replay failure

The full [cycle replayer](evidence/p3/verify-a03-cycle01.py) verified the original
archive, firmware/reboot evidence and inherited browser/host gates, then exited
1 at the frozen full-journal classifier in `verify-h5r2-functional.py`.

That classifier handles nginx startup socket/auth errors only when
`9_000_000 <= __MONOTONIC_TIMESTAMP < 12_000_000`. At **12,075,869 microseconds**,
the new boot retained two nginx messages:

- `connect() to unix:/run/kvmd/api/kvmd.sock failed (2: No such file or directory)`
- `auth request unexpected status: 502`

Four earlier entries at 9.190562, 10.654282 and 10.656283 seconds satisfy its
startup branch. The first 12.075869-second entry instead enters its later
logout/socket-reset branch and fails that branch's exact-message assertion at
line 175. The window was inherited from the accepted H5R2 replayer; it was not
widened after observing this result. The startup deadline itself passed.

This establishes a journal-classification acceptance failure. It does not
establish a production root cause or persistent nginx/kvmd regression. The
original full replay traceback is retained. A separate failure verifier executes
the exact pinned classifier AST on the immutable journal and reproduces the same
assertion at the same timestamp. It does not convert the cycle into a pass.

## Preserved evidence and final decision

The exclusive publisher created `P3_A03_FAILED.json` once after VM replay failed.
Its record vetoes the provisional controller decisions. The original cycle
directory files and original archive were not rewritten. A separate
`p3-a03-cycle-001-vm-replay-failure` directory retains the traceback, replayer
source and journal observations. The appended failure snapshot independently
verifies all 2,548 indexed files and all 2,543 files from the original cycle
archive unchanged. Independent comparison also verifies all 1,927 predecessor
files from the attempt-02 archive unchanged. Attempt 02 and its latch remain
permanently FAILED at `5c58466`, with zero credit.

| Private archive | SHA-256 |
| --- | --- |
| `out/p3-controller-r1/p3-a03-cycle-001.tar.gz` | `58ef027fa82066b505827133b488005aa22d4d15f543b8a73ab96715e02abccb` |
| `out/p3-controller-r1/p3-a03-cycle001-replay-failed.tar.gz` | `689e2442510781009439ff70ded02365b472f1492d27cbee0cf7d046ce91afd2` |

[Independent failure replay](evidence/p3/verify-a03-cycle01-failure.py) and
[sanitized result](evidence/p3/a03-cycle01-failure.json) preserve the FAILED
outcome. Full after-cycle journal review covers 1,129 records. Raw inventories,
browser output, credentials, sealed leaves and private archives stay outside Git.
No P3-A pass, acceptance tag or dependent phase is unlocked.
