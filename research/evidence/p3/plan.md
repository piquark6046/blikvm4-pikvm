# P3 standalone SD stability

Status: **PREPARATION; NOT ACCEPTED** (2026-09-13). P2 attempt 02 is accepted
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
Physical actions proceed one at a time with operator acknowledgment. P3 tests
have not yet run; the acceptance record must remain unaccepted until reviewed.
