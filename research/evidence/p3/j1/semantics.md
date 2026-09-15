# P3-J1 predeclared semantics

Declared after unclassified offline study, before classifier implementation or
classification replay. No target contact. Attempt 03 remains FAILED 0/12 at
bd5640f08bcd9531830d56c5414c24a0eef44ba9. Frozen verifiers are unchanged.

## Evidence and candidates

Use complete journal JSON from a single boot, in nondecreasing target monotonic
order, preserving index and original fields. Reject malformed/mixed-boot inputs.
Inspect every message for ERROR, CRITICAL, Traceback, [error], [crit], segfault,
EXT4-fs error, I/O error, Buffer I/O, Kernel panic, Oops:, checksum error, and every
priority 0–3 record. Unknown candidates reject the journal.

Require exactly one systemd Started witness for each nginx.service and
kvmd.service, exactly one kvmd.htserver listener-ready witness for the precise
/run/kvmd/api/kvmd.sock endpoint, and no service stop/failure/restart or second
service invocation. systemd Started kvmd is NOT socket readiness. kvmd Started must precede
listener readiness; nginx Started and listener readiness must both precede
each logout reset.

## Startup

Require nginx.service, exact complete nginx log grammar for the retained GET /
HTTP/1.1 request, expected client/server/host, /auth_check subrequest and exact
http://unix:/run/kvmd/api/kvmd.sock:/auth/check upstream. Accept only ENOENT
connect() while connecting to upstream and auth request unexpected status: 502
while sending to client. Require matching worker/connection IDs for each pair,
with socket failure no later than its auth failure. No arbitrary 502 or socket
endpoint exception. Require both unit-start witnesses < error < listener-ready.
Reject the entire journal if either class occurs outside this bracket, including
any recurrence after readiness. No absolute-time semantic cutoff or outer bound.

Require later target-journal auth/check 200 success and a login, no crash/restart,
and passing downstream HTTPS/auth/core gates before a qualification consumer may
call this benign. Classifier replay alone reports journal eligibility; it cannot
award cycle credit or replace functional replay. Attempt 01 can establish the
causal sequence but cannot satisfy the separate core-functional prerequisite.

## Logout

Require nginx.service and the exact retained upgraded-connection ECONNRESET
grammar, GET /api/ws or /api/ws?stream=false, and corresponding exact kvmd /ws
upstream. Require readiness before the reset, nearest preceding auth event a
real kvmd logout, nearest following auth event a real kvmd login for the same
user, and kvmd Removed client socket witness between those two auth events.
No timestamp cutoff routes records into this class. Startup/logout grammars
are disjoint. All witnesses must belong to this same boot/service invocation.

## Historical expected results

H5R2 functional-001/002/003: journal eligible, 0 startup errors, 2/3/6 reset
records respectively (cumulative snapshots of ONE boot, not three boots).
Attempt 03 cycle 1: causal startup eligibility only if all six records precede
its actual listener and later auth success exists; known resets require the
same logout rule. Never award attempt-03 credit.
Attempt 01: six causal startup records expected; functional prerequisite
unsatisfied, historical FAILED unchanged.
P2 normal-reboot and final-coldboot text journals: fail closed for qualification
because trusted systemd unit/priority fields are absent. Retain every candidate
and timeline for study. Final-coldboot also includes older deliberate invalid-auth
and restart tests; do not add exceptions for those to this P3 classifier.

## Fixture contract

Reject A–J from the user request; additionally reject missing readiness, wrong
upstream/path, mixed boots, extra readiness/service starts, unknown priority-3
records, and a failed downstream functional gate. Positive cases: real H5R2
boot (no startup errors), sanitized A03 startup and H5R2 logout. Moving the whole
valid causal sequence in time must preserve the result. No fabricated H5R2
startup-error observation.

## Inherited offline timeout (coverage addendum before attempt-04 freeze)

The original even-cycle matrix explicitly retains P2's wait-online timeout.
A01's immutable preboot inventory retains the accepted P2 boot as journal JSON,
including trusted units. Study this additional full capture too. Its deliberate
invalid-auth/restart tests must still reject under P3's no-restart classifier.

For the two exact priority-3 timeout/failure records only, preserve the existing
rule when the caller independently establishes an offline cycle. Require the
journal sequence: systemd starting wait-online < exact wait-online timeout <
exact systemd failed-to-start witness < ssh listening on 192.168.88.2:22 <
systemd-networkd eth0 gained carrier. Require one witness of each, trusted units,
and no earlier eth0 gained-carrier record. This third class is disjoint from
nginx startup and logout; no numeric threshold selects it. Connected-mode
classification rejects it. Offline timing/physical-link gates remain external
and unchanged. Add positive exact-sequence fixture and reject missing carrier,
wrong unit, missing pre-carrier SSH bind and unannounced connected-mode timeout.
