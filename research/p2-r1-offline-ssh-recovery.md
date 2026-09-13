# P2-R1 — offline-Ethernet SSH startup recovery

Status: **Candidate 1 narrow diagnostic PASSED; revised image FROZEN for fresh
P2 attempt 02.** P2 attempt 02 has not started. No baseline tag is created.
[Attempt 01](p2-standalone-sd-bringup.md) remains permanently FAILED, preserved
and pushed as `b19036e` before code changes. Recovery SD is excluded from all
writes. No P3, M6/ATX, RO/overlay work or new core soak is authorized here.

## Exact offline configuration

[Configuration evidence](evidence/p2/r1/offline-config.json) comes from the exact
original public image SHA-256 `873845575255879c13dc5a91aebfdbe269929e2af58b3a71c547661776e3c127`:
read-only loop attachment at 4 MiB, ro,noload mount, exact file/link comparison,
and unchanged whole-image hash. The private receipt proves enrollment changed
only its approved four files plus SSL parent metadata, none of these units or
network files. No running recovery-system command was used.

| Setting | Exact installed configuration |
| --- | --- |
| networkd | systemd `259.5-0ubuntu3.4` |
| OpenSSH server | `1:10.2p1-2ubuntu3.6` |
| Network match/address | eth0; 192.168.88.2/24 |
| Dynamic addressing | DHCP=no, LinkLocalAddressing=no, IPv6AcceptRA=no |
| Name services/routes | no DNS/default gateway; LLMNR=no, MulticastDNS=no |
| RequiredForOnline | routable |
| ConfigureWithoutCarrier | unset, default false |
| IgnoreCarrierLoss | unset, follows ConfigureWithoutCarrier for this configuration |
| SSH ListenAddress | only 192.168.88.2, from 00-blikvm-lab.conf |
| SSH Restart | on-failure |
| RestartPreventExitStatus | 255, vendor unit, no overriding drop-in |
| RestartSec | unset; installed manager documented default 100ms |
| StartLimitIntervalSec / Burst | unset; installed manager documented defaults 10s / 5 |
| SSH Wants | network-online.target; sshd-keygen.service via enablement link |
| SSH Requires | sshd-keygen.service |
| SSH After | network.target, nss-user-lookup.target, auditd.service, sshd-keygen.service, network-online.target |
| SSH start | ExecStartPre=sshd -t; ExecStart=sshd -D $SSHD_OPTS; Type=notify |
| ssh.socket | disabled, not masked; no sockets.target or ssh.service.requires activation link |

The vendor socket unit contains wildcard ListenStream and FreeBind=yes, but it
is disabled. Its leftover package helper bookkeeping and ssh.socket.wants keygen
link do not activate it. No explicit socket preset overrides the default preset
policy; a future preset operation is not current enablement. Candidate 1 neither
enables nor alters this unit. Runtime listeners must still be audited.

sshd-keygen.service is the installed vendor oneshot with ConditionFirstBoot=yes,
ConditionPathIsReadWrite=/etc/ssh and a non-symlink condition; it runs ssh-keygen -A,
remains active after exit and orders Before SSH. The accepted machine-ID first
boot mechanism is unchanged. The ram-root.conf name is historical; its contents
also apply on SD. SSH's condition forbids /etc/ssh/sshd_not_to_be_run (absent).

wait-online is enabled under network-online.target.wants, not Requires. Its
unmodified command has no flags, binds to and runs after networkd, and runs before
network-online.target. Its built-in wait timeout is 120 seconds. No wait-online
drop-in changes it. Wants and ordering do not require successful routability:
a failed wait job can finish, allowing network-online.target and SSH to start.
Later carrier arrival does not re-run a completed network-online target or
repair a failed SSH service automatically.

## Supported semantics versus historical inference

[Version evidence](evidence/p2/r1/version-semantics.json) records execution of the
exact installed ARM64 networkd binary's --version under QEMU, its SHA-256 and
its `Network.ConfigureWithoutCarrier` parser key. The Build VM has the identical
systemd package version; matching local manpage hashes are recorded. Upstream
[v259 network documentation](https://raw.githubusercontent.com/systemd/systemd/v259/man/systemd.network.xml)
confirms the directive permits configuration without carrier and implicitly
enables IgnoreCarrierLoss when unset. DHCP, RA and link-local are already off;
the ordinary static IPv4 address does not use default IPv6/link-local DAD.
RequiredForOnline=routable remains unchanged, so the online wait may still time
out offline. Candidate 1 addresses address availability, not boot-wait duration.

The exact vendor ssh.service excludes main-process exit 255 from restart.
The matching installed systemd documentation and
[v259 service semantics](https://raw.githubusercontent.com/systemd/systemd/v259/man/systemd.service.xml)
confirm that RestartPreventExitStatus wins over Restart=on-failure. It applies
to the main process, not ExecStartPre. This **static restart mechanism is proven**;
an actual bind error/main-process exit 255 in attempt 01 is **not proven**.

The supported failure hypothesis is: no carrier -> networkd leaves static
address unconfigured -> wait-online eventually fails -> SSH starts after the
completed wait with its address absent -> sshd cannot bind -> main process exits
255 -> restart is prevented -> later carrier brings the address and HTTPS back
but does not revive SSH. UART and remote refusal are consistent with this chain;
the lost live journal prevents asserting the intermediate runtime states or
excluding a different SSH failure. Candidate runtime evidence must distinguish
the predicted address/start ordering from a restart-based recovery.

## Candidate 1 and gates

The assembler's explicit `p2-r1-candidate1` revision adds exactly one line under
[Network]: `ConfigureWithoutCarrier=yes`. Keep the restricted SSH listener,
firewall, services, logging, kernel, DTB and all core package files unchanged.
No SSH retry drop-in, DHCP, DNS or gateway is added. Historical public and private
P1 images remain untouched. Independent assemblies and enrollment results will
be recorded below before any expendable-card write.

## Predeclared narrow diagnostic

This is not P2 attempt 02. Positively re-identify the expendable medium and obtain
a new typed destructive confirmation tied to the exact new enrolled image.
Flash with fsync/flush, physically remove/reinsert, compare the complete image
using page-aligned O_DIRECT, verify raw SPL/FIT placement and read-only fsck.
Do not use historical /dev/sdX or diskseq values as current identity.

Capture UART passively from before power application without sending any byte
or interrupting U-Boot. UART/power share a cable in this setup: a hotplug-aware
recorder previously missed SPL/TF-A before device reopen. The user confirmed separate UART power is physically impossible and explicitly
approved this narrow diagnostic exception: preserve the missing early SPL/TF-A
interval as an evidence gap, and require uninterrupted UART capture from systemd
startup through Ethernet/SSH recovery. Never describe the early capture as
complete. The exception applies to this diagnostic only, not P2 attempt 02.

Leave Ethernet disconnected for at least 300 seconds after the observed Ubuntu
login/systemd startup marker, longer than the original timeout, recording bridge
carrier=0 throughout. Then physically reconnect. Poll carrier, ICMP, TCP443,
trusted HTTPS and enrolled SSH independently once per second with bounded probe
timeouts. Define recovery latency as each first success's monotonic timestamp
minus the bridge's first observed carrier-up timestamp; also record the operator
connection timestamp. Poll timing limits measurement precision. Predeclare a
60-second recovery gate after carrier-up for both trusted HTTPS and enrolled SSH.
No reboot, UART command, service repair or configuration change is permitted.

Immediately on first SSH login, archive boot journals for networkd, wait-online,
and ssh; systemctl status/show ssh; networkctl status eth0; IPv4 address/routes;
sshd -T; listening sockets; nftables; boot ID; monotonic timestamps; logging
policy/allocation. Retain complete raw output privately. Require only the approved
SSH address, matching HTTPS restriction/authentication, SSH NRestarts=0, no
status-255 SSH failure/retry, and evidence that the static address existed at SSH
startup. A successful SSH journal listener record for 192.168.88.2 before the first
carrier-up record proves the address was usable for the original bind (no
freebind/socket activation is enabled). A current address alone is insufficient;
if the journals cannot establish this ordering, report an evidence gap.

Repeat one physical Ethernet down/up, hold down 60 seconds, and require the same
60-second automatic recovery gate without service repair. Verify unchanged boot
ID, service process generation, listener/firewall policy and bounded logging.
Preserve any failure and stop. Candidate 2 can be evaluated only if Candidate 1
fails because SSH still starts with its address absent. Do not combine them
without separate evidence that both are necessary.

After a passing and frozen diagnostic, start P2 attempt 02 from zero with a
separate fresh flash, typed confirmation, physical reinsert/full readback and
complete original P2 gates, including cold offline startup, real RW SD root,
artifact/first-boot checks, Chromium/video, HID, RO MSD, USB-PC reconnect,
persistence, normal reboot and post-reboot smoke. Diagnostic boot earns no credit.
No 24-hour soak rerun is needed only if the user-defined narrow-change scope,
LAN/HTTPS/auth and bounded logging regressions and complete P2 attempt 02 pass.

## Offline Candidate-1 artifact results

Final independent builds `out/p2-r1/final-A` and `out/p2-r1/final-B` pass whole-file
cmp for all 9 public output files, including SHA256SUMS. Their source hash
records match the finalized assembler directory. Development A/B also matched;
final A/B include the finalized revision documentation in source provenance.

| Artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| New public raw image | 1,077,936,128 | `1db928494867222308a37507cc37f82f81892849900154275840ac14b2312079` |
| New public compressed image | 69,962,116 | `f9577617339c366ce69ebff2ee60ce541b22948e595cf0e0e3f529d9a588b435` |
| New private enrolled raw image | 1,077,936,128 | `c261a2328594bca90f6a47bc566429a5684c0bf573de0d4089f2843f114eae24` |
| New private enrollment receipt | — | `5c2982a84cd6bead37a76dfb189f71d0144c3545d1a08a006333157c45314084` |

[Reproducibility](evidence/p2/r1/reproducibility.json) verifies raw/compressed
identity, current source hashes, unchanged accepted inputs/contracts/patches,
boot scripts and raw bootloader. All 14,602 public filesystem entries were
validated; comparison to the historical P1 manifest permits exactly the single
network-file change, retaining its ownership/mode/mtime. All other entries are
identical. [Validation](evidence/p2/r1/validation.json),
[fsck](evidence/p2/r1/e2fsck.log),
[credential scan](evidence/p2/r1/secret-scan.json) and
[enrollment separation](evidence/p2/r1/enrollment-separation-scan.json) pass.
All 135 local tests pass, including rejection of network-input drift.

[Sanitized enrollment review](evidence/p2/r1/private-enrollment-review.json)
verifies 14,606 entries and fsck with exactly four approved enrollment files plus
the new SSL directory. Other payloads/metadata and raw boot areas remain identical
to the new public base. Private image, receipt and compression remain under
`out/p1/private/p2-r1-candidate1/`, outside Git. Original public image/compression
hashes were recomputed unchanged; no old published image was patched in place.

Bridge identity was rediscovered using bridge-only commands. Its USB SD reader
currently exposes a 15,634,268,160-byte unmounted card; the physical card identity
and fresh destructive typed confirmation were subsequently supplied by the user. The new diagnostic SD write and initial direct readback have now passed, as
recorded below. No recovery-target contact, diagnostic boot or P2 attempt 02
has occurred. The shared power/UART hotplug limitation now has the explicit diagnostic-only
exception above. Fresh typed destructive confirmation has now been received; the diagnostic
flash proceeds separately from P2 attempt 02. One bridge read timed out in udevadm's pager;
repeating with SYSTEMD_PAGER=cat completed without device or configuration writes.


## Diagnostic flash — write and initial direct readback passed

The operator confirmed the expendable card and recovery separation and supplied
the exact by-id/new-image hash as fresh typed destructive confirmation. Bridge
identity and media guards were rechecked, including current mapping/diskseq,
capacity, reader serial/path, unmounted state, no swap/holders, and exclusion of
bridge system filesystems. Private image/receipt transfer used SFTP with the
configured bridge host-key fingerprint verified; both hashes passed on bridge.

The guarded write completed fsync and flush. The complete page-aligned O_DIRECT
readback compared every one of 1,077,936,128 bytes against the new enrolled image
and matched SHA-256 `c261a2328594bca90f6a47bc566429a5684c0bf573de0d4089f2843f114eae24`.
Frozen raw bootloader extent hashes also match the fully compared image.
[Sanitized write receipt](evidence/p2/r1/diagnostic-flash-write.json) records the
result. Private archive SHA-256:
`26520ac0127bebf1ee149cbb3dda80b6abd0bce14fb94315559afd864931294f`.
The downloaded VM archive hash matches the bridge; archived flash code matches
the VM source. The recovery target was not contacted or modified.

Physical removal/reinsertion, full post-reinsert direct comparison, raw bootloader
checks and physical-media fsck are still pending. Do not move this card to the
target before those checks pass. This flash is solely for the narrow diagnostic;
P2 attempt 02 will require another fresh flash and its own typed confirmation.


## Post-reinsert gate — PASSED

The operator physically removed and reinserted the expendable SD. Fresh identity
guards passed and diskseq changed 19 -> 23. Complete page-aligned O_DIRECT
readback again compared all 1,077,936,128 bytes and matched the exact enrolled
image. A separate 4 MiB direct prefix read matched the image and independently
hashed the SPL/FIT extents. Physical partition e2fsck -fn returned zero; ext4
UUID and PARTUUID match the candidate. No physical filesystem was mounted.

[Sanitized result](evidence/p2/r1/diagnostic-flash-reinsert.json) records these
gates. Private archive SHA-256:
`8d774d95675ac41e2967cb64ec1e61f33bcf51685fc132f9614e863a9ecb9554`.
Bridge and downloaded VM archive hashes agree. The previous pending-reinsert
paragraph records the preceding write-only checkpoint and is now superseded.

Passive reconnect-aware UART and bridge carrier recording were started before
requesting the cold SD swap. They transmit no UART commands or target packets.
The operator must power the target off, preserve the recovery SD separately,
insert this verified diagnostic card, disconnect Ethernet before applying power,
and keep Ethernet disconnected until the recorded 300-second offline dwell is
complete. Early SPL/TF-A capture remains subject to the approved exception;
systemd-through-recovery continuity is mandatory. This is not P2 attempt 02.


## Narrow diagnostic offline boot — dwell passed, recovery pending

The operator powered on the new SD with Ethernet disconnected. UART segment 2
captures accepted Linux at 13:45:00 UTC, the SD PARTUUID command line, systemd
startup at 13:45:04, first-boot key generation and Ubuntu login at 13:45:15.
Capture is uninterrupted from systemd startup. Carrier remained zero throughout
the boot and the measured 330.657 seconds after the login marker, exceeding the
predeclared 300-second dwell. Missing later service markers alone do not prove
service state; networkd/SSH startup ordering remains for live journal review.

[Offline gate evidence](evidence/p2/r1/diagnostic-offline-boot.json) records marker
times and hashes. Private snapshot archive SHA-256:
`c4c91349a2bb17a245de5bbddb284070a8e14ea43df98506ac31b879769dd1a2`.
The VM verified the archive and every member hash listed by its receipt.
Independent recovery probes and immediate enrolled-SSH journal collection are
armed before the operator is asked to connect Ethernet. No UART command or
target service repair occurred. This is still the narrow diagnostic, not P2.

## First automatic recovery — PASSED; carrier cycle pending

Ethernet carrier was first observed at bridge 13:58:21 UTC. Independent probes
measured ICMP 1.019 s, TCP22 1.015 s, TCP443 1.016 s, trusted HTTPS 2.098 s and
enrolled SSH 3.720 s after carrier. First SSH immediately triggered the required
read-only startup collection, completed about 1.609 s after that login probe.
No reboot, service repair, configuration change or UART command occurred.

[Independent VM review](evidence/p2/r1/diagnostic-first-recovery.json) verifies
all 16 archived member hashes. Private recovery archive SHA-256:
`2c9d8a0c75e6308b6d9f6abae975a18d8af212b9b2c32d38a3c799e13f0b0273`.
The exact journals show wait-online timing out at boot +126.808 s; SSH then
listened on 192.168.88.2 at +127.055 s, whereas eth0 first gained carrier at
+801.073 s. Thus SSH's successful restricted bind preceded carrier by 674.018 s.
Its main PID is 259, NRestarts=0, result=success; no status-255 failure/retry
occurred. The vendor RestartPreventExitStatus=255 is still effective.

sshd -T reports only 192.168.88.2:22; live TCP listeners are only that socket and
192.168.88.2:443. ssh.socket remains disabled/inactive. The exact candidate
network file is installed; only the connected subnet route exists. Live nftables
retains the eth0/bridge-source/destination restrictions and default-drop policy.
The accepted volatile 16 MiB/4 MiB journald policy is effective with 4 MiB allocated;
nginx logs are empty. /var/log occupies 24 KiB on SD, including first-login wtmp
and directories; RAM-soak /var/log=4 KiB is not asserted for this SD boot.

Supplemental policy harness extra01 failed because it incorrectly required an
IPv6 sysctl on the frozen CONFIG_IPV6=n kernel. Its files remain unchanged. A
separate extra02 check passed the applicable IPv4 nonlocal-bind=0 check, confirmed
the unavailable IPv6 sysctl against the pinned kernel configuration, and verified
unauthenticated API HTTP401 with normal CA/hostname verification. No image change
was made. These supplemental files will be included in the final diagnostic
archive. The stale target realtime also causes the pre-existing future-password
date warning; monotonic journal timestamps establish ordering without clock repair.

The original attempt's lost journal still prevents direct proof of its exit code.
This candidate's runtime supports the predicted address/startup resolution. The
required controlled carrier down/up is armed; Candidate 1 is not yet frozen or
credited as fully diagnosed, and P2 attempt 02 has not started.


## Carrier-cycle observation re-prepared (2026-09-13)

On the operator's request, expired observation carrier-cycle01 was preserved:
it timed out without any carrier-down event and has no qualification credit.
The first UART recorder finished normally; the subsequent capture gap is explicit,
not evidence of an uninterrupted overnight observation.

Read-only preflight verified the same diagnostic boot ID, SSH PID 259 and exact
start generation with NRestarts=0; nginx remains active with NRestarts=0. Trusted
HTTPS returns 302 with TLS verification result zero. No target repair, reboot,
configuration change or new SD write occurred.

[Re-preparation receipt](evidence/p2/r1/carrier-cycle-reprepare.json) records the
fresh separate carrier-cycle02 and uart-cycle02 monitors. The expired observation,
original UART, supplemental failed/passed policy harness files and new preflight
were archived privately; bridge/VM SHA-256 agrees:
`d80cafd1383edc112538084914ce53b9fc61137ab873ae59b106bf100e7c8f1a`.
Fresh cycle deadline is 600 seconds, with a required 60-second physical down dwell
and the unchanged 60-second automatic recovery gate. P2 attempt 02 is not started.


## Candidate-1 decision and freeze — 2026-09-13

**CANDIDATE 1 NARROW DIAGNOSTIC PASSED.** Carrier-cycle02 observed 97.363 seconds
physically disconnected. On reconnect, trusted HTTPS returned in 2.064 seconds
and enrolled SSH in 3.377 seconds, without any repair. The same boot ID, SSH PID
259/start time and nginx PID/start time persist; both report NRestarts=0. Exact
restricted listeners, inactive/disabled ssh.socket, firewall, static subnet-only
route and candidate network configuration remain in force. Journald allocation
was 4 MiB at first recovery, next-day preflight and post-cycle under the unchanged
16 MiB volatile policy. The new UART segment has no disconnect during the cycle.

[Independent acceptance replay](evidence/p2/r1/verify-diagnostic.py) verifies all
93 member hashes in the final private archive and evaluates both recovery windows,
boot/process continuity, listener/address ordering and retained policy. Its
[sanitized result](evidence/p2/r1/diagnostic-acceptance.json) passes. Final private
archive SHA-256:
`058557cbc659fa7ff922db346b08b75ae8f329e39b8c71b565f7413a4ea31ef6`.
All original failures/expired observations remain archived and uncredited.

The original startup mechanism is sufficiently resolved by this runtime evidence:
SSH successfully bound the approved address before carrier, with no status-255
failure or retry. The lost original journal still prevents direct proof of its
exit code. **Do not add Candidate 2 or an SSH restart override.**

[Candidate freeze](evidence/p2/r1/candidate-freeze.json) fixes the public raw and
compressed images, assembler source hashes and new private enrolled image/receipt.
The only production filesystem delta is ConfigureWithoutCarrier=yes; accepted
Linux, DTB and core packages remain unchanged. Historical P1 stays offline-passed
and its original artifacts remain intact; this revision supersedes them for P2.
Run 04 remains the accepted core soak. No 24-hour rerun is launched for this
narrow fix; the remaining full P2/LAN/auth/logging regression gates still apply.

P2 attempt 02 must now start from zero with a new expendable-card identification,
fresh typed erasure confirmation, fresh write/fsync/flush and physical reinsert/
complete readback. Diagnostic boot and its checks contribute no P2 qualification
credit. M6/ATX, P3 and RO/overlay remain deferred.
