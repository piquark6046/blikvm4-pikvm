# H5R2 prospective harness qualification

P3-S0 independently proves that a fresh production boot restores the exact
attached RO G4 medium. H5R2 uses that boot,
`1c8365c7-90bf-46fb-8db4-5ec06a745a6a`, without reboot between preflights.
H5R1 remains permanently FAILED at `12680f9`; its target prerequisite was false
before Chromium launch. H3 root cause remains UNASSIGNED. H5 remains FAILED.
P2 PASSED, P3 UNACCEPTED; P3-B/C blocked, M6/ATX and RO/overlay DEFERRED.

## Prospective source and runtime

P3-S0 checkpoint `bdd9a61` and prospective H5R2 source `8a7175e` were pushed
following explicit user approval. The bridge verified every source-bundle byte
against the clean published commit before installing the new namespace.
An oversized first functional-bundle transfer was rejected as invalid JSON before
installation, target contact or functional launch. Bounded-part transfer matched
complete SHA-256 `7b0f55f5fcf6172200b66f7a43721c9f26ebbfd71eac04ab3c9874ba8d69d089`.

The new locked account is uid 992 with its sole dedicated group. Byte-for-byte
comparison covers 1,149 runtime files, Node, Xvfb/xvfb-run, launch options,
generated stable Chromium flags, both netns implementations and both H3/H2
permission implementations. Only account/namespace paths and the necessary
Playwright temporary profile differ. The H5R1 netns environment ABI remains.
The four browser protocol sources differ only in namespace references.

The netns-only self-test passes. One target-free about:blank launch passes
prospective contract/argv, clean launch/page/close, no SIGTRAP, permission audit,
whole-leaf sealing and independent archive replay. Its private archive has
SHA-256 `0fc4a91e62c9f65a987231ebc788d90ddb88a224523d45ad319b79cfcb00f6c2`.
The [minimal replay](evidence/p3/h5r2-minimal-001-vm-replay.json) and
[inheritance replay](evidence/p3/h5r2-minimal-inheritance-replay.json) establish
that one sanity run satisfies the inherited-runtime gate. Zero P3 credit.

## Target preconditions and postconditions

Every full functional run checks the same boot, physical accepted SD root,
P2 identities and all 10,690 production/enrollment hashes, unchanged service
generations, no failed service or unexpected target error, exact sole
mass_storage.g4/lun.0 and immutable LUN attributes, API connected=true with the
approved catalog image, and host RO identity plus a complete direct G4 read.
A false condition stops before Chromium without repair. Successful runs must
repeat those attached-state checks after the complete unchanged browser protocol.

Each run retains all 11 MSD stages, eight media/write-protection checks, all 47
HID stages including neutral cleanup, changing 1920x1080 video, three prospective
Chromium contracts/argv records, permission isolation and sealed-run immutability.
The next run requires an independent replay acknowledgment for the preceding
sealed archive. H5R2 earns no P3-A cycle credit.

## Replay reporting correction

The first functional-001 offline replay checked the correct outer archive hash
but reused the variable named expected for a HID event list, corrupting only
the emitted archive_sha256 field. The initial output remains privately retained.
The H5R2 replayer now uses a distinct archive_sha256 argument; the same immutable
archive was independently replayed before its acknowledgment was issued. No
bridge harness, browser protocol, raw evidence or acceptance threshold changed.
H5R1 historical sources/results were not modified.

## Current status

**H5R2 independently accepted.** All three preflights start and end with the
same attached RO G4 state. Their independent replays retain 24 full media
checks, 141 HID stages and nine functional Chromium launch contracts/argv
records. Every run has six unique video samples. All 10,690 hashes and service
generations match on the same boot. The aggregate review verifies 2,140
predecessor-file comparisons unchanged in the final archive.

[Acceptance](evidence/p3/h5r2-acceptance.json) earns zero P3-A cycle credit.
The immediate target inventory after acceptance passes; cycle 1's own declared
reboot remains to be executed. Local suite: 156 tests, two privileged skips;
real bridge netns and permission execution are independently retained above.

| Run | Private archive SHA-256 |
| --- | --- |
| functional-001 | `4cf2e4f9b890639d2f832b3dc917b4f52ab6d67c28c6a37e6a6755d4fa7fe627` |
| functional-002 | `6073424557af5d67d813da1fddc1aa968fd31907e4d68daba999af3d430de707` |
| functional-003 | `830608ff1f8f5b398b88f1c64cdbb320f38961ee602f3caf2f8108982314c1e6` |

H3 root cause remains UNASSIGNED. H5 FAILED. H5R1 FAILED because its target
prerequisite was false before launch. H5R2 prospectively qualifies the browser
harness from a proven boot state. No product tag.

Subsequent P3-A status: [attempt-02 cycle 1 failed before issuing its reboot](p3-a02-cycle01-failure.md)
on a new controller state-publication bug. H5R2's accepted evidence and status
remain unchanged. No cycle credit or production runtime regression is inferred.
