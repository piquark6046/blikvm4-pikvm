# P3 standalone SD stability

Status: **STOPPED — P3-H2 FAILED before first browser launch; attempt-02 reboot sequence NOT STARTED; P3 NOT ACCEPTED** (2026-09-13). P2 attempt 02 is accepted
at `1fa1a7c8a4c53639dfd38e32e24c256c8682afd7`, revision `p2-r1-candidate1`.
The annotated `standalone-sd-core-kvm-baseline` tag already exists locally and
on origin at that exact commit (tag object `025b6eccf3d1e84a54d73d82a1af92c82c651bbd`).
P2 attempt 01 remains permanently FAILED. This is not another M8-F soak.
M6/ATX, writable MSD and RO/overlay remain DEFERRED.

Frozen public image: `1db928494867222308a37507cc37f82f81892849900154275840ac14b2312079`.
Frozen private enrolled image: `c261a2328594bca90f6a47bc566429a5684c0bf573de0d4089f2843f114eae24`.
No image regeneration or production-file modification is authorized by this plan.

## Predeclared sequence

P3-A uses the accepted expendable card. Exactly 12 clean standalone reboot
cycles run in order. Odd cycles 1,3,5,7,9,11 keep Ethernet connected throughout.
Even cycles 2,4,6,8,10,12 disconnect Ethernet before reboot and reconnect only
after the offline gate. The matrix cannot change after results are observed.
Each cycle stops for evidence review before the next cycle; a failure stops
the sequence without service repair or an automatic retry.

Before every reboot retain boot ID, machine ID, public host-key hashes, physical
root device, UUID/PARTUUID, SD CID, journal allocation and failed units, plus the
full volatile journal. Capture UART before requesting reboot; require SPL,
TF-A/BL31, vendor U-Boot, SD boot script, kernel and systemd in order. Require
physical `/dev/mmcblk0p1` RW ext4 with accepted UUID/PARTUUID, accepted Image/DTB,
unchanged production/enrollment hashes, stable machine/SSH identity, restored
kvmd-owned uStreamer, nginx, gadget and MSD helper, exact MJPEG 1920x1080 30/1,
trusted HTTPS, enrolled SSH and effective bounded journald configuration.

Connected startup deadline is 180 seconds. Offline startup gate requires a
continuous UART trace through systemd/login, zero bridge carrier, and 300 seconds
offline after login (within 600 seconds of reboot). After reconnect, trusted
HTTPS and enrolled SSH must recover within 60 seconds of observed carrier.
Retained boot-journal timestamps must prove SSH bound `192.168.88.2` before carrier;
require `NRestarts=0` and no manual service repair. The inherited offline
`systemd-networkd-wait-online.service` timeout is classified as in accepted P2;
it is not permission to ignore any other failed unit.

Every boot runs real Chromium changing-video and host-observed keyboard,
absolute and relative mouse checks, plus RO MSD attach/read/eject/reattach and
the exact G4 whole-image hash. Reuse P2 harness contracts and retain raw evdev,
SCSI, frame and browser results. Review full journals and kernel/USB logs,
including high-severity messages, before counting a cycle. Successful harness
completion is provisional until independent archive replay.

P3-B follows passing P3-A. Exactly three abrupt power cuts, only in stable
multi-user userspace on the expendable card:

1. Steady idle: after successful smoke and inventory, dwell 60 seconds with
   stable services, video/HID/MSD and logging, then remove power without shutdown.
2. Active appliance: two authenticated video clients, browser/API activity,
   periodic HID, RO MSD and normal bounded logging; dwell 120 seconds of verified
   active load, then cut without a special preceding sync.
3. Disposable RW activity: unique 64 KiB sentinel under `/var/tmp`, file fsync
   and parent-directory fsync, with recorded SHA-256; a separate writer repeatedly
   replaces a bounded 8 MiB scratch file, never the sentinel. Cut after 30 seconds
   of verified writer activity. Scratch contents have no exact recovery contract.

Each fully-off interval is 15–60 seconds, measured from confirmed removal to
restoration. Record operator actions and the last available bridge/target wall
and monotonic timestamps; do not mislabel an operator acknowledgment as an
electrically measured cut time. Never cut during flashing, firmware/bootloader
execution, filesystem maintenance or recovery-media use. Capture first available
post-power UART, full post-boot journal, ext4 replay and complete identity. Root
must mount RW automatically; no manual fsck or service repair. Expected journal
replay alone is not failure. Fail on lost/corrupt sentinel, mount failure, RO
fallback, recurring ext4 I/O/checksum errors, changed production files, or
persistent USB/UVC/MUSB/SCSI/HID/kernel/service regression. Each case requires
core smoke and a subsequent clean reboot with healthy filesystem and smoke.
Archive evidence before normal scratch/sentinel removal and directory fsync.

P3-C follows passing P3-B. A second physical expendable card must be independently
identified and distinct from card 1. Keep recovery SD physically separate. Before
writing: whole-device by-id, model, serial, capacity, logical/physical sector
sizes, mounted/system/recovery rejection and typed confirmation binding that
exact by-id to the frozen enrolled-image SHA-256. No new enrollment. Write with
dd, fsync and flush; physically remove/reinsert the reader; O_DIRECT-read every
one of 1,077,936,128 image bytes and require the frozen digest, raw SPL/FIT checks
and read-only fsck. Insert only while target is fully off. Cold boot Ethernet-off,
require the same automatic recovery, then full representative P2 regression:
physical RW root, frozen files/enrollment, generated identity, trusted HTTPS/auth,
real browser video, two clients each >=27 fps for 120 seconds, all HID modes,
RO MSD, physical USB-PC reconnect, bounded logging, normal reboot and smoke.
Compare generated identity within card 2 across its reboot, not across cards.

P3-D transfers all private archives by authenticated SFTP to the VM and verifies
archive hashes, every retained member, replay scripts and full available UART/
journals. Retain every failure separately. No stability acceptance commit/tag
until all 12 cycles, 3 cases with clean follow-ups and the second-card regression
pass independent review. Then publish a sanitized acceptance record, commit and
annotated `standalone-sd-stability-baseline` tag. Qualification covers CORE KVM
on RW SD only; it is not full M8. RO/overlay is the next optional phase only.

## Evidence constraints

P2 used a user-approved early-firmware UART exception for shared power/UART
reenumeration. P3-A requires a complete continuous firmware trace. For physical
power-on capture, retain exact availability/gaps and seek a decision if evidence
cannot satisfy the P3 gate; do not silently inherit or broaden that exception.
Physical actions proceed one at a time with operator acknowledgment. The preceding
plan was frozen before the first reboot; its original bytes are retained in
[evidence/p3/plan.md](evidence/p3/plan.md). The results below do not change it.


## Attempt 01 — stopped after cycle 1 (2026-09-13)

**FAILED; zero passing P3 cycles.** The connected clean reboot restored enrolled
SSH and trusted HTTPS automatically. Continuous UART captured the full vendor
SPL/TF-A/U-Boot/SD/kernel/systemd chain. Startup and failure-preservation inventories
both matched all 10,690 frozen production and enrollment files, exact 1080p30
MJPEG, physical RW ext4 root/UUID/PARTUUID, machine ID and SSH host public keys.
There were no failed systemd units on the new boot.

The first browser MSD stage completed target/host checks, including the exact
G4 image hash, but Chromium then failed to read its bridge acknowledgment file:
`EACCES` on `001.ok`. Tar metadata and live stat independently show root-owned
mode `0600`. The bridge controller's `077` umask propagated to the child harness,
while Chromium ran as the unprivileged bridge user. This is a **bridge harness
permissions failure**, not evidence of SD-media, ext4 crash-recovery, startup
policy or core KVM failure. Complete core behavior remains unqualified for this
cycle because the remaining browser/MSD/HID stages did not execute.

The sequence stopped immediately. No later reboot, service repair, filesystem
repair, power cut, second-card write or recovery-SD operation followed. The target
remains on the failed attempt's otherwise healthy standalone boot. The failure
cannot be erased by a later successful test.

Private archive `out/p3/preparation/a01-evidence.tar.gz` was transferred using
SFTP with the configured bridge host-key pin and independently verified on the VM:
SHA-256 `dde56c3bf3ab1d14006c601c8c8a05343c353b11c385f9b8a33755837ed5e57a`,
85 retained files, 3,300,831 bytes. The [replay](evidence/p3/verify-attempt01.py)
and [sanitized result](evidence/p3/attempt01.json) preserve the failed outcome.
The separate preflight archive has SHA-256
`2aab01a080ab178fad5862c5c8af6a7c5383bd26c71f7ae6b382f3f6447a6f10` and
24 verified files. It preserves the earlier truncated-manifest transfer failure,
which stopped before contacting the target and has no reboot credit.

Independent full postboot journal review covers 552 records. All 27 warning/
high-severity lines match inherited classifications. Six nginx application-level
critical/error messages occurred at boot seconds 9–12 while readiness probes
arrived before the kvmd socket existed; subsequent automatic recovery occurred
without repair. These lower-case application messages were reviewed explicitly,
in addition to the automated priority/uppercase-error scan. UART's two endpoint
`-108` messages occur during shutdown before SPL; the vendor TF-A RSB message
also occurs in the accepted P2 normal-reboot archive. Neither recurs as a
persistent failure after this boot. No unexpected ext4/I/O/kernel failure was
found in the retained postboot evidence; incomplete smoke is still not a pass.

A proposed VM-only controller correction sets `umask=0o022` for browser harness
children while retaining the parent's private evidence umask. A VM cross-user test reproduced the `0600` denial and verified `0644` access
with the proposed child umask; see [permission check](evidence/p3/harness-permission-check.json).
It has not been uploaded or exercised on hardware. A fresh attempt must preserve this failure,
preflight cross-user acknowledgment access and then start the same 12-cycle
matrix from cycle 1. No accepted production file needs modification for this
instrumentation correction. The stable-image tag must not be created now.


## Attempt 02 preparation — bridge permission correction

Attempt 01 is frozen by commit `d7e6734`, FAILED with `accepted_cycles=0/12`.
The proposed child umask alone did not meet the stronger private-input boundary.
The bridge now has a dedicated `p3-browser` account (uid 995/gid 983, no
supplemental groups), an isolated root-owned context, root-owned read-only
credential copies, and a fresh NSS database containing only the public enrolled
CA. The original private files and attempt-01 evidence contents are unchanged.
No target artifact, configuration, enrollment or qualification assertion changes.

The bridge-only [installer](../lab/p3-browser-prepare.py) pins the original
MSD/HID harness hashes, changes only browser identity and evidence permissions,
and resolves the browser dependency directly. The [launch permission gate](../lab/p3-browser-permissions.py)
records uid/gid, owner/group/mode, resolved paths and effective access under the
actual browser account before every launch. Evidence directories are `0750`,
credentials `0640` root/browser-group, private directories `0750`, and root
acknowledgments `0644`; there is no world-writable evidence directory. The
bridge home changes from `0750` to `0751` solely for dependency traversal.

The first bridge-only permission unit check caught an intermediate dependency
symlink through a `0700` directory before any browser or target contact. The
installer now links directly to the resolved public dependency tree. This
negative check remains in the [permission inventories](evidence/p3/attempt02-permission-inventories.json),
alongside two passing fresh-directory checks including executable parents,
create/rename/read/cleanup and `EACCES` on attempted write-only opens of both
original and copied credential files. The writes do not truncate or alter data.
These are permission tests, not browser preflights or P3 cycles.

The two actual browser preflights and attempt-02 start inventory are pending.
P3-B/P3-C have not started. P2 remains PASSED; P3 remains NOT ACCEPTED.


## Attempt 02 preparation — stopped at browser preflight (2026-09-13)

**PREFLIGHT FAILED. Attempt-02 reboot sequence NOT STARTED; zero reboot
cycles consumed and `accepted_cycles=0/12`.** The second preflight was stopped
after an effective-access check proved browser uid 995 could write the first
preflight's `browser-msd` and `browser-hid` evidence directories. Both remained
owned by uid 995/gid 983 with mode `0750`. Their root-owned parent was not
writable, but traversal still allowed modification inside the child directories.
The first permission gate checked original P3 evidence and private inputs; it
failed to include all prior browser-run evidence. Commit `81b3f61` therefore
remains an **insufficient harness correction**, not authorization to reboot.

The first run completed browser functionality: Chromium 145.0.7632.6, trusted
HTTPS and enrolled login, 11 MSD stages, 8 independent storage checks and
19 media transitions with the exact G4 digest, 47 HID stages and six distinct
video frames at the retained 1080p30 setting. Both browser harnesses exited
zero, no browser processes remained, target service generations were unchanged,
and all 10,690 target hashes plus 99 protected bridge hashes matched. Its
[functional replay](evidence/p3/attempt02-preflight01.json) is supplemental;
it does **not** accept the complete permission boundary or earn P3 credit.

Full first-preflight journal review covered 1,191 records. The six inherited
early nginx errors remain classified as in attempt 01. Three additional nginx
`recv() failed (104: Connection reset by peer)` messages occurred on upgraded
WebSockets during the deliberate logout stages. Retained kvmd journal entries
place each reset between logout/socket removal and subsequent successful
reauthentication; browser stale-session and neutral-HID assertions passed.
The replay requires those specific causal witnesses, rather than ignoring all
nginx errors or relying on severity alone.

The second run was stopped during MSD smoke. Its original `in_progress`
controller record remains unchanged alongside an explicit `boundary-failure.json`.
The transient unit's reported exit status is not treated as a completed browser
run. No browser processes remain. There was no third preflight, reboot, service
repair, target configuration change, power cut, second-card action or reflash.
The post-stop inventory matched all 10,690 production/enrollment files, the same
physical root and SD CID, boot ID, machine/SSH identities, and service generations.
All 99 protected bridge hashes and all 482 live first-preflight evidence files
were independently compared and unchanged.

Both private archives were transferred via pinned-host SFTP and independently
verified on the VM, including every manifest member:

- First preflight: 492 members; SHA-256
  `c528cd34d02e0a939edd4bbb7dfec7be6e7ff5dc83854472604154e4bfea0f6f`.
- Stopped second preflight: 125 members; SHA-256
  `be15a52352e74b222e219a0ead96f10aa523eefc26d4f4bbe266afa4fad0d644`.

The [failure replay](evidence/p3/verify-preflight02-failure.py) and
[machine-readable checkpoint](evidence/p3/attempt02-preflight-failure.json)
preserve the failed boundary and zero-cycle status. The 135 local tests passed;
they do not override this live permission failure.

A future bridge-only correction must seal completed/aborted evidence against
the browser account and inventory every sibling evidence tree before launch,
including preparation-test outputs. It must verify protected paths cannot be
modified through writable ancestors. That correction and another browser
preflight have **not** been applied or run after this stop. Two fully passing
fresh-directory preflights and a new immediate target start inventory are still
required before cycle 1. The original 12-cycle matrix is unchanged.

P2 remains PASSED. P3-A is not passed; P3 remains NOT ACCEPTED. P3-B and P3-C
remain NOT STARTED; M6/ATX, writable MSD and RO/overlay remain DEFERRED. No tag
was created. The user-requested stop on preflight failure is in effect.


## P3-H2 — evidence isolation stopped FAILED (2026-09-13)

**FAILED before the first Chromium launch; zero browser-smoke completions and
zero reboot cycles.** The expanded actual-UID auditor caught a historical
attempt-01 output omitted from the migration seal list:
`/home/user/blikvm-msd/p3-context/a01-smoke/browser-msd`. Its preexisting
ownership was root:root and its mode was **0777**. Browser uid 995/gid 983,
with only group 983, successfully created the disposable probe when creation
was required to fail. The first 150 operations met their expectations; operation
151 failed the boundary. No functional browser stage ran. `preflight-002` and
`preflight-003` have NOT STARTED, and no retry or corrective resealing followed.

The probe remains in place as negative evidence. It is a new zero-byte file;
its creation changed the historical directory's mtime/ctime. The independent
before/after comparison found no removed files, no changed preexisting file
contents, and no other protected-path metadata changes. This is a protected
evidence namespace mutation and a failed gate, not a claim of complete
permission isolation. The frozen attempt-01 and both earlier preflight archives
retain their exact previously recorded hashes and failure classifications.

Before this launch gate, the new bridge-only implementation created a separate
root-owned context at `/var/lib/blikvm-p3-h2`. It separates browser output from
controller records and read-only acknowledgments, uses exclusive no-follow
controller publication, rejects symlinks/hardlinks/special output entries,
and records effective syscall results plus ancestor ownership/mode/xattrs.
No broad permission grant was introduced. The migration archived and sealed
five old permission-test directories, three old dedicated-browser smoke leaves,
and the old browser home. Those nine original archives precede their metadata
changes. The unused active leaf was also archived and sealed during failure
preservation. Original archive metadata and sealed working-copy records are
retained separately. These implementation paths are **unqualified**: the
migration coverage was incomplete and the complete syscall gate did not pass.
The frozen failed candidate is retained in [the lifecycle/auditor](../lab/p3-h2-boundary.py),
[context preparation](../lab/p3-h2-prepare.py), and
[preflight controller](../lab/p3-h2-preflight.py). Do not run these as an accepted
harness or remove the controller's `FAILED.json` latch to resume qualification.

Fresh pre-launch and failure-preservation target inventories independently
match all 10,690 production/enrollment hashes against the immutable attempt-01
startup evidence, accepted P2 root UUID/PARTUUID, SD CID, machine/SSH identity,
boot ID `eecefe38-98a3-406c-9260-3e51de321ffe`, and SSH/core service generations.
No browser processes remain. The retained full post-stop journal contains
1,479 records; its nine error messages exactly match the previously reviewed
six early nginx errors and three deliberate-logout socket resets. No new error
message appeared. No reboot, target repair, target configuration change,
SD reflash, power cut, second-card operation or M8-F rerun occurred.

Private archive `out/p3-h2/h2-failed-evidence.tar.gz` was downloaded by pinned-host
SFTP and independently verified on the VM: **3,445,267 bytes**, SHA-256
`1bb8f7076d86de563381e2736169698589c03f728f5d09c6fac148943b42b332`.
All 78 indexed files and ten original metadata archives replay successfully as
**FAILED_CONFIRMED**, including the exact deployed candidate sources. See the
[failure result](evidence/p3/h2-failure.json) and
[independent replay](evidence/p3/verify-h2-failure.py). This replay verifies the
failure and preservation; it does not accept the boundary or a functional smoke.

The local suite ran 140 tests: 139 passed and one POSIX ACL fixture was skipped
because this VM filesystem returned EINVAL when creating the synthetic ACL.
The live auditor inventories POSIX ACL xattrs and rejects any encountered ACL;
no live ACL acceptance is inferred from the unavailable local fixture.
The local symlink, ancestor substitution, hardlink, FIFO and exclusive-publication
checks passed. Local checks cannot override the live failure.

The three earlier checkpoints `d7e6734`, `81b3f61`, and `d064d7f` were scanned,
reviewed, and pushed to origin/main in that order, with remote readback confirming
`d064d7f`. The sole pattern hit was the existing synthetic private-key rejection
test fixture, not private material. [Push/scan record](evidence/p3/h2-historical-checkpoints.json).
No tag was created.

The newly requested three-run H2 gate supersedes the earlier proposal for two
preflights; neither failed preparation nor this stopped H2 run earns any credit.
P3-A attempt 02 remains NOT STARTED with `accepted_cycles=0`. P3-B/P3-C remain
NOT STARTED. P2 remains PASSED; P3 remains UNACCEPTED. M6/ATX, writable MSD and
RO/overlay remain DEFERRED. The stop-on-failure boundary remains in effect.
