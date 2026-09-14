# P3 standalone SD stability

Status: **STOPPED — P3-H5 minimal-001 FAILED before Chromium launch;
H3 root cause: UNASSIGNED; attempt-02 reboot sequence NOT STARTED;
P3 UNACCEPTED** (2026-09-13). P2 attempt 02 is accepted
at `1fa1a7c8a4c53639dfd38e32e24c256c8682afd7`, revision `p2-r1-candidate1`.
The annotated `standalone-sd-core-kvm-baseline` tag already exists locally and
on origin at that exact commit (tag object `025b6eccf3d1e84a54d73d82a1af92c82c651bbd`).
P2 attempt 01 remains permanently FAILED. This is not another M8-F soak.
M6/ATX, writable MSD and RO/overlay remain DEFERRED.

Frozen public image: `1db928494867222308a37507cc37f82f81892849900154275840ac14b2312079`.
Frozen private enrolled image: `c261a2328594bca90f6a47bc566429a5684c0bf573de0d4089f2843f114eae24`.
No image regeneration or production-file modification is authorized by this plan.

Current methodology is the [prospective H5R1 plan](evidence/p3/h5r1-plan.md).
The [H5 plan](evidence/p3/h5-plan.md) remains frozen historical evidence.
Historical H4/H4b control prerequisites below describe those checkpoints only;
they are no longer gates. The earlier successful attempt-02 browser preflight
is a **HISTORICAL FUNCTIONAL REFERENCE**, never an exact control. No further
reconstruction of unknown historical DISPLAY/XAUTHORITY/argv/environment is
required. H5 preserves rather than supersedes H3's FAILED record.

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


## P3-H3 — ancestor isolation passed permission tests; Chromium preflight FAILED (2026-09-13)

**H3 FAILED; zero P3 credit.** The three permission-only transitions passed,
but `chromium-preflight-001` failed at the first Chromium launch. Chromium
PID 15228 started and exited with **SIGTRAP** before Playwright could create a
page or complete any UI, login, video, MSD or HID smoke stage. No second Chromium
launch occurred. Runs 002/003 and P3-A attempt 02 were not started.

The prelaunch global syscall auditors passed, including the auditor run by
uid 995 immediately before the actual Chromium launch. The root controller
subsequently raised `RuntimeError('missing launch gate')` because its expected
MSD second-launch audit was absent. That secondary controller error does not
replace the retained primary browser launch failure. The crash root cause
is **unassigned**. No browser retry, source repair, target service restart,
reboot, reflash, power cycle or historical-descendant permission repair followed.
The bridge `controller/FAILED.json` latch remains in place.

### H2 checkpoint preservation

Checkpoint `0ef54c7124253458615bf117c7a70848861c4c4c` remains the immutable H2
failure checkpoint. Its original archive replay again returned FAILED_CONFIRMED.
The complete 1,067-file tracked tree passed the public private-material scan
after review of the unchanged synthetic scanner-rejection fixture. Fetch,
review, push and remote readback confirmed that origin/main already held that
exact checkpoint; push reported `Everything up-to-date`. No tag was created.
See [the scan and push record](evidence/p3/h3-h2-checkpoint-scan.json).

### Legacy quarantine and clean namespace

Read-only bridge discovery found four legacy P3 working roots:

- `/home/user/blikvm-p3`
- `/home/user/blikvm-msd/p3-context`
- `/var/lib/blikvm-p3-browser`
- `/var/lib/blikvm-p3-h2`

Before any move, the controller checked the four frozen failure-archive hashes,
created complete lstat/xattr/file-hash manifests and verified four additional
whole-root archives. The manifests retain original absolute paths, numeric
owner/group, modes, inode/device/link counts, mtime/ctime, ACL/xattr information,
symlink targets and every regular-file hash. Legacy symlinks were recorded
without traversal. It then renamed each complete root under the **single
root:root mode 0700** ancestor `/var/lib/blikvm-p3-legacy`. No old-path alias was
created, and no legacy descendant was chmod/chown-ed. Old paths are mapped to
new paths in `controller/quarantine.json`.

In particular, the historical `p3-context/a01-smoke/browser-msd` remains **0777**
and the uid-995 zero-byte H2 probe retains its contents, ownership and identity
in both the frozen pre-move archive and quarantined working copy. Its permissions
cannot bypass the inaccessible legacy ancestor. Working-root rename metadata
is recorded separately; it does not rewrite any original immutable archive.

The new namespace is `/var/lib/blikvm-p3-h3`, root:root 0755:

| Path | Boundary |
|---|---|
| `controller/` | root:root 0700; manifests, logs, archives and failure latch |
| `input/` | root-owned read-only browser inputs; no legacy evidence links |
| `input/acks/` | root-owned, browser-readable protocol acknowledgments; browser mutation denied |
| `active/` | root:root 0711; traversal allowed, sibling creation denied |
| `active/<nonce>/` | sole current writable capability root, uid 995/gid 983 0700 |
| `sealed/` | root:root 0700; completed leaves retain descendant ownership/modes |

The installed runtime, frozen P3 scripts, public NSS trust data and required
credential inputs are copies, with no symlinks into legacy evidence. Credential
copies are root:983 0640 under a root:983 0750 directory. Fixed input/source/private
manifests exclude the explicitly generated acknowledgment stream, whose writes
are controller-only and whose bytes are included in the evidence export.

The [H3 boundary helper](../lab/p3-h3-boundary.py) independently walks the whole
reachable evidence namespace under uid 995; inaccessible ancestors terminate
traversal. Root records the complete namespace/ACL/stat/realpath inventory and
mount information and enforces the exact active-leaf count. Actual create,
write-open, truncate, rename and unlink attempts supplement the boundary checks;
current-leaf create/write/fsync/rename/unlink succeeds. Source/private roots and
repository ancestors are also checked. Unexpected ACLs fail closed. Completed
leaves are fsynced, manifested, archived and verified before a same-filesystem
atomic rename into `sealed/`; descendant chmod/chown is not the sealing mechanism.

Controller publication uses exclusive no-follow operations; browser JSON reads
reject symlinks, hardlinks and special files. The candidate also validates
browser requests against the frozen 11-stage MSD and 47-stage HID protocol
before using names in privileged evidence paths. Every Chromium launch, including
the planned MSD reopen, has an actual-UID global syscall gate. These functional
integration paths remain **unqualified** because the first launch failed.

### Permission-only evidence and failed browser evidence

`perm-001`, `perm-002` and `perm-003` each passed the full UID audit, created a
harmless browser-owned fixture under an intentionally mode-0777 descendant,
were archived/verified and renamed into `sealed/`, then passed a zero-active-leaf
audit. Each later transition also denied access through the previous sealed
ancestor. Independent VM replay verified **35,595 operations in six audits**,
all four legacy archives, the original H2 probe, and preserved 0777 descendants.
These tests contacted neither the target nor Chromium and earn zero P3 credit.
See [permission replay](evidence/p3/h3-permission.json) and
[its independent verifier](evidence/p3/verify-h3-permission.py).

The failed first Chromium leaf was archived with all 25 original members and
renamed whole into `sealed/chromium-preflight-001`. A separate preservation
audit denied direct write-open/truncate/rename/unlink of every sealed browser
file and the preserved legacy probe, as well as ancestor traversal/creation.
No uid-995 process and no active leaf remains. The browser failure archive
independently replays as **H3_FAILED_CONFIRMED**: 234 indexed files and 23,857
additional syscall operations, including prelaunch and post-failure audits.
All permission-snapshot file bytes remain unchanged in that final archive.
See [failure replay](evidence/p3/h3-failure.json) and
[its independent verifier](evidence/p3/verify-h3-failure.py).

Both archives were transferred by authenticated, pinned-host SFTP and hashed
independently on the VM. The MCP download tool returned binary as text; the
retained local artifacts use the verified binary SFTP transfer instead.

| Private VM archive | Bytes | SHA-256 |
|---|---:|---|
| `out/p3-h3/permission-only.tar.gz` | 25,297,300 | `2158a52d913639d4547f950e54d6d7a2c0132d0fcb5bea539319c5ecfa2c71b0` |
| `out/p3-h3/h3-failed.tar.gz` | 28,238,682 | `78cb138eca5698b29286931df1c47c350b3526c13560f35a812babc51ef48752` |

The matching bridge exports are under `/home/user/blikvm-p3-h3-exports`, mode
0700 and inaccessible to uid 995. Full raw/private evidence remains outside Git.
The local suite ran **144 tests: 143 passed, one ACL fixture skipped** because
the VM cannot create the synthetic POSIX ACL. The live auditor does not waive
ACL rejection. Local path-hardening fixtures passed for symlinks, parent
substitution, hardlinks, FIFOs, exclusive publication and unknown 0777 descendants.

### Target continuity and stop boundary

Independent prelaunch/failure-preservation inventories match all **10,690**
production/enrollment hashes, accepted P2 physical root UUID/PARTUUID and SD CID,
machine/SSH identities, boot ID `eecefe38-98a3-406c-9260-3e51de321ffe`, and SSH/core
service generations. The full 1,502-record retained target journal has the same
nine previously classified errors and zero new error messages. Protected bridge
input/source/private bytes and metadata are unchanged across this failed run.
The temporary bridge HDMI test-source process was stopped by normal harness
cleanup; no browser functional stage completed.

H3 is **FAILED, not accepted**, despite its successful permission-only phase.
There is no H3 acceptance checkpoint or tag. P3-A attempt 02 stays unstarted at
`accepted_cycles=0`; P3-B/P3-C remain unstarted and blocked. P2 remains PASSED;
P3 remains UNACCEPTED. M6/ATX, writable MSD and RO/overlay remain DEFERRED.

## P3-H4 — offline runtime isolation blocked (2026-09-13)

**H4 NOT QUALIFIED; H3 remains FAILED; zero P3 credit.** Checkpoint `1895be8`
remains immutable. The bridge-only investigation disproves the proposed removal
of SUID bits from the frozen Chromium helper. It does not assign H3's crash
root cause. No target contact, reboot, reflash, H4 functional preflight or P3-A
attempt-02 cycle occurred. P2 remains PASSED; P3 remains UNACCEPTED;
P3-B/P3-C remain blocked; M6/ATX, writable MSD and RO/overlay remain DEFERRED.

The exact source tree is `/home/user/blikvm-lan/out/kvmd-web/browser`, resolved
by both the pre-H3 browser input and H2's retained runtime symlink. H2 itself
never launched Chromium: the earlier attempt-02 first preflight supplies the
successful functional evidence. H3 used its distinct copy at
`/var/lib/blikvm-p3-h3/input/context/out/kvmd-web/browser`.

Both trees have 1,235 entries. Every common regular file has identical content.
The full private `out/p3-h4/browser-runtime-metadata-diff.json` records relative
paths, SHA-256, numeric owner/group, full st_mode/type, symlink targets, link
counts, all xattrs and getcap output. `getfattr` was unavailable; Python's
no-follow listxattr/getxattr APIs collected xattrs directly. H3 changed every
entry's owner/group to root, changed 640 full modes, and dereferenced the two
Playwright CLI symlinks. These two type changes are not executable content
corruption. No entry in either tree has SUID/SGID/sticky bits or xattrs.

The actual helper name is **`chrome_sandbox`**, not `chrome-sandbox`:

| Input | uid:gid | Full st_mode | Capabilities |
|---|---|---|---|
| Source | 1000:1000 | 0100755 | none |
| H3 copy | 0:0 | 0100755 | none |

The helper hash is identical in both trees:
`206aa30eeb399b1d10fdf345106b315be01deded548243eb7263c8af2773ab88`.
The `chrome` and `chrome_crashpad_handler` hashes also match. The source was
**not root-owned setuid**, and H3 did not change 04755 to 0755.

### Preserved H3 crash review

H3's retained Playwright launch argv contains `--no-sandbox`, supplied by the
historical Playwright default. H4 did not rerun that argv. H3 browser.log is
empty; browser-result.json retains launch/cleanup records and SIGTRAP but no
sandbox, namespace, crashpad, NSS or profile fatal message. The retained
controller journal only adds the secondary missing-launch-gate exception.
The PID-specific journal and bounded kernel-journal query have no entries.
`coredumpctl`, GDB and stackwalk tools are unavailable on the bridge. Apport
recorded PID 15228, signal 5, core limit zero, and discarded its package-level
report because this executable does not belong to a package.

A separate **51,376-byte Crashpad minidump** survives under H3's sealed
runtime HOME. The dump and its metadata were copied privately without altering
H3. The VM extracted thread 15228, signal 5, and twelve saved instruction/frame
pointer module offsets; the first is `chrome+0x633662b`. This is a bounded AMD64
RBP-chain inspection, not a symbolized/CFI-unwound backtrace. No usable fatal
annotation was recovered. Public evidence contains only sanitized module
offsets, never raw dump memory or environment. Structure interpretation uses
[Breakpad's format definitions](https://github.com/google/breakpad/blob/main/src/google_breakpad/common/minidump_format.h)
and [AMD64 context definition](https://github.com/google/breakpad/blob/main/src/google_breakpad/common/minidump_cpu_amd64.h).
H3's root cause remains **UNASSIGNED**; SIGTRAP alone does not identify it.

### Independent sandbox-enabled matrix

Diagnostics used new namespaces, never `/var/lib/blikvm-p3-h4` or H3's active
leaf. A transient root controller entered an empty network namespace before
launching Xvfb/Playwright as uid 995, gid 983, supplementary groups `[983]`.
Only a down loopback interface existed; target connectivity was absent.
`chromiumSandbox: true` was explicit; captured launch argv contains no
`--no-sandbox`. Each case used fresh HOME/TMP with the same simple layout;
D additionally reproduced H3's fresh HOME/.pki/nssdb ownership and mode layout.

| Case | Runtime | HOME/TMP | Result |
|---|---|---|---|
| A | Exact source | Simple fresh | SIGTRAP; no page |
| B | Exact H3 copy | Simple fresh | SIGTRAP; no page |
| C | Fresh `cp -a` source copy | Simple fresh | SIGTRAP; no page |
| D | Same preserved copy | Fresh H3 NSS/layout | SIGTRAP; no page |

All four stderr logs report **`No usable sandbox!`**. Matching kernel audit
records show the `unprivileged_userns` AppArmor profile denying `sys_admin`
during Chromium namespace setup. This demonstrates the present sandbox-enabled
launch blocker, not H3's historical crash cause: H3 had disabled sandboxing.
No host AppArmor/sysctl policy or runtime metadata was repaired. A/C did not
pass; the proposed A/C-pass versus B-fail classification is unsupported.

The first diagnostic controller had a separate setup error: umask 0077 reduced
the requested cases-parent 0711 to 0700, so Xvfb could not create its log.
Chromium never launched there. That failed namespace and logs remain intact;
the corrected controller ran the complete matrix in a second new namespace.
Neither diagnostic attempt is an H4 functional preflight or P3 credit.

Exact invocation/environment, Chromium argv/hash, stderr, Xvfb logs, 50 ms
process snapshots, wrapper status, browser signal, page-creation results and
kernel journal are privately archived. All four browser wrappers returned 1;
no uid-995 process remained. The preserved copy's complete manifest equals the
frozen source, and both source and H3 runtime manifests remained unchanged.
Diagnostic case trees were archived and verified before atomic rename below
their root-owned 0700 private ancestors; uid-995 traversal was then denied.
This is diagnostic preservation, not the unrun H4 global permission gate.

### Replay and stop boundary

[Independent verifier](evidence/p3/verify-h4-offline.py) authenticates both
private archives, verifies all 76 indexed diagnostic members, rechecks runtime
and copy equality, validates every case's sandbox-enabled argv and failure,
reconstructs the sanitized minidump frames, and compares H3's FAILED latch
against its immutable prior archive. [Public result](evidence/p3/h4/offline-result.json).

| Private archive | Bytes | SHA-256 |
|---|---:|---|
| `out/p3-h4/offline-diagnostics.tar.gz` | 214591 | `284c44c1e62f526b1bf36db42940a0356c55f38c2805877634b8b1afa8da99c0` |
| `out/p3-h4/h3-crashpad-private.tar.gz` | 11019 | `129c99656aa0c39346c2b77e4591e787136a2b987f40c85b9fd53e90b457943e` |

Both transfers used authenticated pinned-host SFTP and matched bridge hashes.
Raw scripts are included in the diagnostic archive, including the failed
first controller. H3's latch and historical evidence were not repaired.

H4 clean-namespace preparation is **NOT STARTED** because H3 root cause was
not demonstrated and minimal sandboxed launch failed. Runtime integrity and
global evidence permission qualification, two minimal passing launches, three
functional preflights, qualification checkpoint, start inventory and P3-A
attempt 02 remain unstarted. No baseline tag or H4 qualification checkpoint
was created. The sandbox-enabled matrix is a SEPARATE APPARMOR FAILURE MODE, not an
H3 reproduction or an advancement gate. H3 historical argv contains
`--no-sandbox` from normal Playwright launch semantics. H3 root cause is
UNASSIGNED. P3-H4b must first reconstruct and replay the historical H2 good
control twice, then the H3 failed control in fresh diagnostic namespaces.
SUID stripping hypothesis: DISPROVEN. Target contact: none. Qualification
credit: zero. AppArmor and sandbox flags must not be changed as workarounds.

Validation: the offline verifier returned `H4_OFFLINE_BLOCKED_CONFIRMED`.
The local suite ran 144 tests: 143 passed and one preexisting synthetic POSIX
ACL fixture was skipped. These checks authenticate the diagnostic findings;
they do not qualify H4 or award P3 credit.

## P3-H4b — historical good-control identity unresolved (2026-09-13)

**P3 remains UNACCEPTED; H3 root cause remains UNASSIGNED. No browser
reproduction probe has started.** The sanitized H4 negative-result checkpoint
`b800439` was pushed before H4b bridge inspection, without a tag. It explicitly
classifies SUID stripping as DISPROVEN and the sandbox-enabled A–D matrix as
a SEPARATE APPARMOR FAILURE MODE. `1895be8` remains immutable.

The requested successful H2 control conflicts with the immutable evidence.
H2 archive `1bb8f7076d86de563381e2736169698589c03f728f5d09c6fac148943b42b332`
contains a FAILED prelaunch permission audit, zero stages, and no browser
result or harness log. Its archived wrapper prepares a fresh runtime HOME,
but that configuration never launched Chromium. The successful earlier
attempt-02 preflight at `81b3f61`, archive
`c528cd34d02e0a939edd4bbb7dfec7be6e7ff5dc83854472604154e4bfea0f6f`,
used `runuser` account HOME without the explicit fresh-HOME override. Its
browser result records Chromium `145.0.7632.6`; its browser logs are empty
and do not preserve the generated argv. These are distinct historical facts,
not interchangeable successful controls. The intended successful custom-HOME
archive has been requested from the user.

[Archive recovery](evidence/p3/h4/recover-launch-contracts.py) authenticates
five private archives without executing their code. It generates the requested
[H2 contract](evidence/p3/h4/h2-launch-contract.json),
[H3 contract](evidence/p3/h4/h3-launch-contract.json), and
[launch difference report](evidence/p3/h4/h2-vs-h3-launch-diff.json).
They are **incomplete historical contracts**, with unknown fields explicitly
marked and `exact_reproduction_ready=false`. Archived source intent is
distinguished from observed argv and process identity. Current host state is
never substituted for missing historical environment, Node identity, or mount
flags. An exhaustive effective-environment differential is not yet possible.

The concrete source delta remains: H2 has no explicit TMPDIR override; H3
exports browser-owned `runtime-tmp`. H2's inherited TMPDIR is unknown, and
its launch never occurred. The prepared H2 and H3 NSS databases have identical
hashes for `cert9.db`, `key4.db`, and `pkcs11.txt`. Other recorded differences
include runtime copying and metadata, HOME and cwd paths, acknowledgments,
the prelaunch JS audit, and ancestor isolation. None assigns crash causality.
D1 remains the first declared probe after valid controls are established.

Read-only bridge inspection used the configured ssh-mcp profile. No UART
session, target connection, browser launch, runtime mutation, or package
installation occurred. [Current observations](evidence/p3/h4/h4b-bridge-readonly.json)
retain safe Node/Xvfb hashes and versions, mount flags, account identity, and
Chromium/Playwright identities. Playwright `1.58.2` package bytes match the
frozen H3 package hash. These observations do not establish bridge-global
drift without corresponding historical evidence and valid control replay.

[Private-dump analysis](evidence/p3/h4/h3-crashpad-analysis.json) recovers
SIGTRAP, thread 15228, `chrome+0x633662b`, and the minidump's ELF build ID
`3693ce542c8bad6e9045e9f05df6241a3ec45cd4`. The build ID matches the binary
whose SHA-256 matches frozen H3. Existing `addr2line` returns no source lines;
nearest exported names are insufficient to identify internal functions or a
CHECK/FATAL site. Saved RIP and bounded RBP-chain offsets remain the only
usable stack evidence. No raw dump or private environment is published.

The [minimal about:blank probe](../lab/p3-h4b-blank.cjs) is prepared and syntax
checked; its local incomplete-contract rejection was checked without loading
Playwright. No browser launch occurred. It uses normal `chromium.launch({headless:false})` without
manual sandbox flags, requires a complete reviewed contract, checks pinned
module/binary identity and uid/gid/groups, and requires external network
isolation and debug capture. The external controller, namespace mapping, and
argv comparison must be completed after resolving the historical control;
the probe's own page success would only be pending argv replay.

This is a historical-evidence blocker preceding decisions A–D. It is neither
bridge-global drift nor H3 nonreproduction: no valid controls were run.
H2-control runs 1/2, H3-control, D1–D7, syscall tracing, and H4 qualification
remain unstarted. H3 FAILED.json is untouched. P2 remains PASSED; P3-A attempt
02 remains unstarted; P3-B/P3-C remain blocked; M6/ATX and RO/overlay remain
DEFERRED. Target contact and qualification credit are both zero.

H4b validation: five archive SHA-256 checks and contract recovery passed; the
prior H4 archive replay still passed. Node syntax and fail-closed incomplete
contract checks passed locally. The preceding checkpoint suite passed 143
tests with one existing skip. These are offline diagnostic checks only.

## P3-H5 — prospective substrate stopped before first browser launch (2026-09-13)

**H5 FAILED, zero credit. H3 root cause: UNASSIGNED.** The forensic conclusion
is frozen: H3 SIGTRAP at `chrome+0x633662b`, exact Chromium build identity and
private Crashpad archive remain retained; SUID stripping is DISPROVEN and
sandbox-enabled AppArmor denial is a separate failure mode. `b800439` and
`eadd900` remain historical checkpoints. No exact successful historical browser
argv/environment exists. H4/H4b had no target contact or browser reproduction.
The earlier successful preflight is a HISTORICAL FUNCTIONAL REFERENCE only.

The new H5 namespace was prepared without changing H3 or legacy descendants,
historical FAILED latches, or the old `p3-browser` account. `p3-browser-h5`
is locked, shell `/usr/sbin/nologin`, uid 994/gid 982, groups `[982]`, and HOME
equals its dedicated `/var/lib/blikvm-p3-h5/home` (owned 994:982, mode 0700).
Root-owned controller/sealed ancestors are 0700, input is read-only to that UID,
and the active parent is root-owned 0711. A fresh public-CA-only NSS database
has no private keys. The public Chromium/Playwright runtime was copied from
the frozen root-owned H3 input tree with modes preserved; no generic Chromium
chmod or old browser home/cache reuse occurred.

Before the probe, contract SHA-256
`cac55c25be2b1332211e806cbeac4c4edb1c2dda70f163d31e446e515a80755d`
recorded 1,235 runtime entries with hashes/ownership/modes/xattrs, executable
identities and package versions, account and ancestor metadata, NSS inventory,
the minimal environment, exact Xvfb wrapper and frozen Playwright API.
Versions remain Node v22.22.1, Playwright 1.58.2 and Chromium 145.0.7632.6.
TMPDIR/XDG_RUNTIME_DIR were absent. No manual sandbox flags were introduced.

`minimal-001` ran under transient systemd unit
`blikvm-p3-h5-minimal-001.service`. The controller used `unshare --net`, brought
loopback up, and checked one interface with `ip` before dropping privileges.
The Node probe then asserted that `/sys/class/net` contained only `lo`, but
observed `enp1s0`, `lo`, and `wlo1`. It exited 1 at that assertion, before loading
Playwright, serializing the in-process launch contract, running the immediate
JS launch audit, or calling `chromium.launch`. There is no generated Chromium
argv, browser context/page, or SIGTRAP from this probe. The preparation-only
`chrome --version` command is not a browser session or qualification launch.

This is a new H5 probe failure. Source review shows the controller isolated
the network namespace but inherited the existing sysfs mount; the sysfs-based
check therefore used an unsuitable interface view. That explains the assertion
path, not H3's crash. Actual in-process namespace identifiers were not retained
because the assertion preceded provenance serialization; the archive does not
certify a completed network-isolation/launch contract. No corrective retry was
performed, and H5's original controller/probe bytes remain frozen.

The pre-probe and post-seal actual-UID audits passed 21,511 operations in total.
The completed failure leaf and fresh NSS home contents were archived with
original metadata and atomically renamed behind the 0700 sealed ancestor.
Explicit traversal/mutation checks of that sealed leaf were denied. No H5 UID
process remained. Complete retained before/after protected manifests match,
including H3/legacy and original private/repository input roots. These permission
results do not pass H5. No target connection was made, so no fresh target
inventory or continuity claim is substituted for the missing functional phase.

Private archive `out/p3-h5/h5-failed.tar.gz` was transferred using SFTP with the
configured bridge host-key pin. SHA-256:
`304bdf020fdb6df9039fe459c392b6c22e16b9f8a04bd52900974430458bc0da`;
611,585 bytes, 35 indexed files and a separately verified seven-member sealed
leaf archive. [Independent Build VM replay](evidence/p3/verify-h5-failure.py)
returned [H5_PRELAUNCH_FAILURE_CONFIRMED](evidence/p3/h5-failure.json).
The source/dirty-state provenance note is explicitly retrospective; the runtime
contract and uploaded plan preceded the probe. No complete in-process launch
contract or generated argv is claimed.

`minimal-002`, `minimal-003`, all three functional preflights, H5 acceptance,
and P3-A attempt 02 remain NOT STARTED. The H5 FAILED latch remains installed.
P2 remains PASSED; P3 remains UNACCEPTED; accepted_cycles=0/12. P3-B/P3-C remain
blocked, M6/ATX and RO/overlay DEFERRED. No acceptance checkpoint, product tag,
reboot, reflash, or target repair was performed. Local validation: 144 tests,
143 passed with one preexisting skip; Python/Node syntax checks passed. Those
tests did not cover the live network-namespace/sysfs distinction.


## P3-H5R1 — corrected prospective namespace observation (2026-09-14)

H5 remains permanently FAILED at aebd3c7 with zero P3 credit. H3 root cause
remains UNASSIGNED. H5R1 is a separate prospective harness qualification; its
[plan](evidence/p3/h5r1-plan.md) preserves all historical failed namespaces.

The new Python/Node gates observe the current network namespace through
netlink and Node os.networkInterfaces(), record namespace identities before
and after privilege drop, and reject external interfaces/addresses/routes
and inherited socket descriptors. Sysfs is informational only. A separate
netns-only self-test must pass before the first minimal launch. Subsequent
minimal runs require a VM replay acknowledgment tied to the prior archive.

[Local validation](evidence/p3/h5r1-local-validation.json): complete suite
151 tests (two privileged tests skipped in that unprivileged invocation);
the separate privileged H5R1 suite passes all seven tests. The real VM test
observed only lo through netlink/Node while inherited sysfs exposed
docker0/enp1s0/lo/proton. No browser or target contact in VM validation.
Source must be committed, pushed and clean before any bridge deployment.
Live H5R1 qualification has not yet started at this source checkpoint.

H5R1 source `ac73300f7b2633b36f0f8cde383845414282daad` was pushed and verified
clean before deployment. The fresh account is UID 993/GID 981. The netns-only
self-test passed with one isolated namespace across privilege drop, lo-only
netlink/Node observations, no inherited sockets, and informational inherited
sysfs enp1s0/lo/wlo1. The first deployment transport invocation failed before
source installation; its prematurely started preparation unit exited with
ENOENT without executing H5R1 code. That unit is retained. Subsequent verified
source installation and the first actual runtime preparation succeeded.

[Minimal-001](evidence/p3/h5r1-minimal-001.json) completed all six stages with
clean browser exit, no SIGTRAP, prospective contract/generated argv, unchanged
protected inputs, no remaining UID processes, and archive/atomic sealing.
The initial VM verifier stopped on literal Python-vs-JavaScript JSON equality:
1,282 metadata ctime_ns/mtime_ns values have JavaScript Number serialization
rounding. This was a VM verifier failure, not a browser retry. The revised
verifier explicitly reproduces JSON.parse/stringify and still verifies the
prospective SHA-256 against the exact original contract bytes; no metadata
fields are ignored. The unchanged archive independently passes. The initial
failed replay is retained in this record. All runs remain zero P3 credit;
H5R1 is not yet accepted and no target contact has occurred.

[Minimal-002](evidence/p3/h5r1-minimal-002.json) and
[minimal-003](evidence/p3/h5r1-minimal-003.json) independently passed on the
same pushed `ac73300` runtime/controller. [Stable launch comparison](evidence/p3/h5r1-minimal-comparison.json)
passes across all three. Profile, X display/auth, leaf/protocol paths and
netns identities are explicitly classified as ephemeral. All three earn zero
P3 credit. The separately frozen functional adaptation now prepares a fresh
context while preserving the qualified runtime; target continuity must pass
before its first functional launch. No target contact at this checkpoint.
