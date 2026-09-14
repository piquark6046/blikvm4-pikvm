# P3-A controller R1 and fresh attempt 03

Attempt 02 remains permanently FAILED, zero cycle credit, at
`5c58466f24701de3e7d2574f6b9328329749d26e`. Its controller, latch,
cycle directory, archive and replay are unchanged. H5R2 remains independently
ACCEPTED and will not be rerun. P2 PASSED; P3 UNACCEPTED; M6/ATX and RO/overlay
DEFERRED. Rehearsal earns zero P3 credit.

## Immutable publication contract

The unchanged H2/H3 exclusive publisher retains O_EXCL, O_NOFOLLOW, pinned
directory descriptors, fsync and owner/mode checks. R1 is a new controller;
the failed old controller remains available for exact-byte regression replay.

`cycle.json` is a declaration, with no evolving result. `start.json`,
`pre-reboot.json`, `reboot-request.json`, `startup-recovered.json`,
`firmware-chain.json`, `pre-browser.json`, `msd-result.json`, `hid-result.json`,
`cycle-final.json` and `result.json` are distinct immutable records. Planned
reboot timestamps explicitly do not assert that a request was issued.
Supporting inventory, transport, audit and protection records have distinct
stage paths. In-memory dictionaries may change; published bytes may not.

Finalization gathers sealing errors before publishing either terminal record.
Each terminal record has one publication site, is attempted once, and is never
retried even if publication fails after writing bytes. `P3_A03_FAILED.json`
has one publication site after finalization and vetoes every provisional
decision. A missing final/result record also prevents acceptance. An I/O failure
that prevents even the latch from being written must be treated as a failed,
incomplete run, never retried. No record awards credit; independent replay does.

## Publication verification

`lab/p3-publication-rehearsal.py` loads the actual controller function AST,
without running hardware-bound module initialization. It executes the complete
connected-cycle lifecycle, including inventory and attached-media publication
sites. Target subprocesses, device reads, audits, browser processes and sealing
are fixture actions. Real subprocess and socket creation are forbidden during
execution. The production exclusive publisher writes into temporary directories.

For each call the ledger checks every previously published byte string, records
the destination before attempting publication, and retains original SHA-256s.
Cases cover success, pre-reboot, reboot request, startup recovery, firmware,
MSD, HID, sealing, both terminal publication sites, combined HID/sealing failure,
and a result publication exception after bytes have been written. Tests verify
that the intended stage was actually reached. A pinned copy of the unchanged
old controller reproduces three attempts to publish cycle.json, the first
rejection before the reboot command. No old evidence is reused for credit.

The supplemental AST report lists every explicit publish destination and
rejects duplicate constant cycle destinations; declaration, final and result
must each have exactly one site. The independent archive verifier imports no
controller code, checks source identities and all ledger hashes, inspects
checkpoint/failure semantics, and verifies the expected fixture stage coverage.

## Deployment and live gates

VM and fresh bridge-only rehearsals must independently replay before target
contact. The bridge rehearsal does not use the production H5R2 namespace.
After full local tests and a public-file secret/private-material scan, commit
and push all corrected source, tests and this plan to origin/main. Deployment
provenance must name that exact clean pushed commit and hash every installed
source file. No working-tree controller may execute a live cycle.

`p3-a03-prestart.py` creates a fresh immediate-inventory namespace. Before target
contact it requires byte/metadata-exact accepted H5R2 runtime/input manifests.
It then reuses the accepted read-only inventory and attached-MSD gates, compares
identity and 10,690 hashes to accepted H5R2 functional-003, and enforces unchanged
boot/service generations. It never normalizes target state. Any failure creates
the new attempt-03 failure latch and stops before cycle 1.

This first corrected controller implements connected cycle 1 only, matching the
failed controller's bounded scope. It does not claim to implement offline cycles.
The original 12-cycle matrix is unchanged: odds connected throughout; evens
disconnected before reboot, 300 seconds offline after UART login within 600
seconds of reboot, then SSH/HTTPS within 60 seconds of restored carrier. Each
later controller slice must satisfy the same publication rehearsal and clean
pushed-source gate before use. No cycle may be skipped, substituted or credited
before independent replay. Failure stops attempt 03 immediately.

Cycle 1 must retain the complete firmware chain, physical RW SD root, enrolled
identity/hashes, attached RO startup MSD, SSH/HTTPS, exact MJPEG 1080p30, real
Chromium changing video, keyboard and both mouse modes, neutral cleanup, all
RO MSD/eject/reattach checks, bounded logging and full journal/kernel review.
The new archive replayer reads the immutable checkpoints, then applies the
unchanged accepted H5R2 browser/host replay gates to this cycle's new boot ID.

P3-A can pass only at 12/12 independently accepted cycles. P3-B follows that
pass; P3-C follows its frozen prerequisites. Physical actions remain one at a
time with operator acknowledgment. No reflash is part of P3-A.

## R1 rehearsal results

The final VM archive and bridge namespace
`/home/user/blikvm-p3-controller-r1-rehearsal-20260914-02` independently pass
13 executions each, including the pinned historical controller failure, with
378 original published-file hashes checked per archive. See
[VM replay](evidence/p3/controller-r1-vm-replay.json) and
[bridge replay](evidence/p3/controller-r1-bridge-replay.json). The earlier
`-01` rehearsal remains retained; source-copy provenance checks were tightened
before the final `-02` rehearsal. Both are zero-credit fixture runs.

Final archives remain private under `out/p3-controller-r1/`. Binary connector
download was unsuitable; a JSON byte-array copy transferred through configured
SFTP reconstructed the archive exactly, matching the bridge SHA-256 before replay.
No target contact, reboot, Chromium launch or H5R2 rerun occurred during R1.

[Local validation](evidence/p3/controller-r1-local-validation.json): 163 tests,
161 passed and two existing skips; the separate privileged namespace suite
passes all eight tests. Its first invocation failed on an incorrect local Node
path and is retained privately; using the discovered executable passes. The
public source/test/plan/result scan found no secret or private material. The
immutable attempt-02 archive still matches its frozen SHA-256.
