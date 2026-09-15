# P3-J1 — causal journal classifier qualification

**P3-J1 PASSED — offline classifier qualification, zero P3-A credit.** Attempt 03 remains
permanently FAILED, 0/12, at `bd5640f08bcd9531830d56c5414c24a0eef44ba9`.
The failure latch, cycle files, archives, traceback and frozen H5R2 verifier
remain unchanged. No target contact or production-service changes.

## Journal study

[Study extractor](evidence/p3/j1/study.py) authenticates complete private archive
SHA-256 values and reads inventories without extracting or executing archived
code. It retains unclassified, machine-readable target-monotonic timelines in
`out/p3-j1/study-002/`. Raw records, auth details and full witness messages remain
private. Each timeline records source member and journal hashes, original record
indices, service milestones, all nginx/kvmd messages and every error/high-severity
candidate. This includes listener, auth success, login/logout and socket-removal
records, without assuming that a systemd Started message means socket readiness.

| Retained capture | Records | nginx Started (us) | kvmd listener (us) | Startup errors / logout resets |
| --- | ---: | ---: | ---: | ---: |
| H5R2 functional-001 | 1148 | 7862562 | 13322594 | 0 / 2 |
| H5R2 functional-002 | 1804 | 7862562 | 13322594 | 0 / 3 |
| H5R2 functional-003 | 2462 | 7862562 | 13322594 | 0 / 6 |
| P3-A01 cycle 1 | 552 | 8403949 | 13079974 | 6 / 0 |
| P3-A03 cycle 1 | 1129 | 8559808 | 13102601 | 6 / 1 |

The H5R2 captures are cumulative snapshots of **one boot**, not independent
startup repetitions. They contain no startup socket/auth errors. Positive
H5R2 fixtures preserve that fact; no synthetic error is presented as observed.

The A03 disputed pair at **12075869 us** follows nginx startup and precedes the
actual listener witness at **13102601 us**. The journal then records auth/check
401 at 13520997 us and later auth/check 200 and successful login. A 401 proves a
responding auth endpoint, not successful authentication; the classifier requires
the later 200 and login. A01 has the same causal ordering, but its incomplete
functional smoke still prevents qualification.

Two accepted P2 archives were also studied. Normal-reboot has eight ENOENT/auth
records, including records at 12032688 and 12034708 us before readiness at
12845294 us. Its text format lacks trusted unit/priority fields and cannot
satisfy P3's metadata requirement. Final-coldboot text includes deliberate
invalid-auth and service-restart tests outside P3's semantics. Both full text
captures fail closed for P3 qualification; P2 acceptance is unchanged.
A01's preboot JSON additionally preserves that accepted P2 boot with trusted
metadata (2282 records). It independently supports the inherited offline timeout
witnesses; its full deliberate auth/restart workload also rejects under P3.

## Why the listener message is a readiness witness

The retained target hash manifest matches the VM's accepted source bytes:

- `kvmd/htserver.py`: `563a055191d6eccbfd8834b9ba4c3d23864f72c8b8a2d9025d94663a7715d0c2`
- `aiohttp/web.py`: `27348d99e8e0e46e987850279088197f2b6a6d4f3ab0dbbce38c982a6a14a6ab`

kvmd binds the Unix socket and calls aiohttp with its logging callback.
aiohttp awaits each site's `start()` before printing `Running on`; kvmd logs
that message through the callback. This supports the listener interpretation.
There is no separate journal event asserting the exact filesystem creation
instant, and none is invented.

## Predeclared rules and independent replay

[Semantics](evidence/p3/j1/semantics.md) precede implementation/replay.
[Candidate classifier](../lab/p3-j1-classifier.py) matches full nginx message
grammars, exact endpoints, trusted units and same-boot causal witnesses. Paired
ENOENT/auth records must fall after both unit starts and before listener
readiness. Any post-readiness recurrence rejects the entire journal. There is
no 12-second split, substitute cutoff or fitted outer bound.

WebSocket resets require the exact request/upstream path, preceding logout,
subsequent same-user login and a kvmd Removed-client-socket witness between them.
The original even-cycle offline timeout remains a separate, explicitly enabled
rule requiring exact wait-online, SSH pre-carrier and first-carrier witnesses.
It cannot be accepted in connected mode.

[Standalone verifier](evidence/p3/j1/verify.py) recomputes every candidate with
an [independent implementation](evidence/p3/j1/reference.py), comparing exact
classification and witness indices. Per-record private output includes full
message, unit, timestamp, reason and complete witnesses. Unknown priority 0–3
or error-pattern records reject. Twenty-seven sanitized fixtures cover A–J,
missing/duplicate readiness, wrong paths/units, mixed boots, unknown priority-3,
time translation and offline timeout prerequisites. No classifier output grants
cycle credit. Downstream HTTPS/auth/core and unchanged-generation gates remain
mandatory.

[Functional replay adapter](evidence/p3/j1/functional.py) pins the unchanged
H5R2 verifier SHA-256 and replaces only its journal-classification section in a
VM-only code view. Its archive, browser, HID, MSD, mode and identity gates remain
in place. Replaying A03 this way is classifier validation only and cannot
retroactively accept its cycle.

## Validation result

The independent corpus replay and all 27 fixtures passed. Full inherited
functional replay passed H5R2 functional-001/002/003 and A03 cycle 1, preserving
zero credit in every adapter result. The unchanged failure verifier again
confirmed A03 FAILED and verified 2548 indexed files, including all 2543 original
cycle files unchanged. The local suite passed 166 tests with two existing skips.
The original publication lifecycle rehearsal, including the frozen old-controller
failure, passed. No frozen source was edited.

[Sanitized classifier result](evidence/p3/j1/result.json) and
[functional replay result](evidence/p3/j1/functional-result.json) retain source
and archive hashes. Private per-record classifications are under
`out/p3-j1/replay-freeze/`; complete unclassified timelines remain separate.

Attempt 04 has not started. R1 implements connected cycle 1 only. Extending it
for the unchanged even-cycle offline matrix would add execution logic beyond
the user's classifier/evidence-plumbing-only change restriction. That scope
question must be resolved before the attempt-04 controller can be frozen;
there is no authority to silently bypass the offline cycles or edit tooling
mid-attempt. No P3-A, P3-B or P3-C credit follows from P3-J1.

## Replay commands

```sh
python3 research/evidence/p3/j1/study.py /tmp/j1-new-study
python3 research/evidence/p3/j1/verify.py /tmp/j1-new-replay
python3 research/evidence/p3/j1/functional.py
python3 research/evidence/p3/verify-a03-cycle01-failure.py
python3 -m unittest discover -s tests
```

Output directories must be new. Original private archives are never rewritten.
P2 PASSED; H5R2 ACCEPTED; P3 UNACCEPTED; P3-B/C blocked;
M6/ATX and RO/overlay DEFERRED.
