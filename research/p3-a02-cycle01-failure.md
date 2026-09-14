# P3-A attempt 02 — cycle 1 controller failure before reboot

**FAILED, stopped, zero accepted cycles.** P3-S0 and H5R2 remain accepted
preparation/harness evidence with zero P3-A credit. P2 remains PASSED; P3 remains
UNACCEPTED, P3-B/C BLOCKED, M6/ATX and RO/overlay DEFERRED. H5/H5R1 remain FAILED;
H3 root cause remains UNASSIGNED. No tag.

## First failure and responsibility

The new VM-built cycle controller at `170056f` incorrectly used the inherited
append-only `publish()` function for successive updates to `cycle.json`.
The helper correctly opens with O_CREAT | O_EXCL | O_NOFOLLOW; it is not an
update API. Initial state publication succeeded. After the read-only attached
preboot gate passed, the controller attempted to publish planned reboot metadata
to the same existing file and received `FileExistsError(17, 'File exists')`.
This controller integration bug was introduced in the new cycle controller.
The local prelaunch tests covered refusal paths but missed this publisher
contract on the normal execution path.

The exception occurred BEFORE the subprocess that issues systemctl reboot.
The in-memory planned request timestamps were subsequently written into the
separate FAILED latch. They are **not evidence of an issued reboot**.
The immutable original cycle.json remains in_progress. The separately published
result.json and P3_A02_FAILED.json record FAILED. Finalization attempted the same
invalid cycle.json update and also failed. None of these files was overwritten
or repaired to reconcile their states.

No reboot request record, recovery probe, startup inventory, Chromium process,
browser stage or active browser leaf was created. Continuous passive UART opened
successfully and captured zero bytes before its explicit bridge-side stop.
The full controller journal records the FileExistsError. No reboot or browser
retry, service restart, media attach/eject or failure-latch removal occurred.

## Runtime continuity and evidence

Preboot, automatic failure-preservation and separate read-only postfailure
inventories retain boot `1c8365c7-90bf-46fb-8db4-5ec06a745a6a`, physical accepted
SD root/identity, unchanged production service generations and all 10,690
production/enrollment hashes. The exact G4 catalog path remains attached,
API connected=true, ro=1 and all frozen attributes correct. Full direct host
media reads before and after match the accepted image SHA-256. This failure is
in the bridge controller, not evidence of a production MSD startup regression.

Private archive: `out/p3-h5r2/p3-a02-cycle001-failed.tar.gz`, 19,316,856 bytes,
SHA-256 `4fa747be4901cc17d78ace87febc363a0287cfa4493086831a481a682c12cc5b`.
The P3-A failure latch SHA-256 is
`59a841dabcb8998c9e5ab56adb44d1dff8619b7580b37ccce9b5803f6255cf6b`.
[Independent replay](evidence/p3/verify-a02-cycle01-failure.py) authenticates the
archive/index, preserves the contradictory initial/final records, reproduces
exclusive-publication rejection offline, verifies source ordering before the
reboot subprocess, and rechecks runtime continuity and all H5R2 predecessor
archive file bytes. [Replay result](evidence/p3/a02-cycle01-failure.json).

The failed controller source is unchanged. No replacement namespace or repaired
controller has been deployed. P3-A attempt 02 is latched FAILED at cycle 1,
with zero actual cycle reboots and **0/12 accepted cycles**. Later cycles stop.

Checkpoint validation: 159 local tests pass (two privileged tests skipped).
The six retained application-error records are byte-identical in timestamp and
message to the already-classified H5R2 records; no new target error appeared.
The controller source remains unchanged, and the public result scan passes.
