# M7 Ubuntu 26.04.1 ARM64 bring-up

Status: **PASSED**, including the final 20-consecutive-clean-reboot gate. M6 GPIO/ATX is **DEFERRED**, not passed.
No PiKVM userspace, peripheral expansion or final storage layout is in scope.
M5 remains frozen at `linux-7.2.3-usb-gadget-baseline` (`3fc6138`).

## Source verification and builder

Ubuntu Base archive: `ubuntu-base-26.04.1-base-arm64.tar.gz`, SHA-256
`5a1906794ced63a71a8119c3f211ef5f0bbe0a243001b4bbd41fdf80c5b219fd`.
Canonical's signed SHA256SUMS verified with the Build VM Ubuntu archive
keyring, signing fingerprint `843938DF228D22F7B3742BC0D94AA3F0EFE21092`.
Raw verification is retained under `out/ubuntu/downloads/`.
The package source is the dated `20260906T000000Z` Ubuntu snapshot.
`build/ubuntu/` is a separate AMD64 containerized builder; kernel compilation
is never invoked by rootfs construction. Initramfs transport provides a read-write RAM root without writing the recovery SD.

## Proven kernel exception

The frozen M5 config disables CGROUPS, FHANDLE, FUTEX, EPOLL, SIGNALFD,
TIMERFD, EVENTFD, INOTIFY_USER, MULTIUSER and UNIX98_PTYS. These are concrete
gaps for systemd, glibc and SSH. systemd's [upstream requirements](https://github.com/systemd/systemd/blob/main/README)
explicitly list the event and cgroup facilities. The additive
`build/ubuntu/linux-systemd.config` adds these plus service namespace,
seccomp and filesystem ACL/xattr support. M5 artifacts and DTB are retained;
only the separate M7 Image is rebuilt incrementally. M5 uses built-in drivers
with CONFIG_MODULES=n, so there is no modules archive to install.

## Negative build result: emulation registration

The first rootfs attempt failed before extraction. Its binfmt registration
incorrectly used printf's format string to emit binary NUL bytes. The kernel
parser truncates at raw NUL bytes, losing the AArch64 architecture discriminator;
native process creation failed with ELOOP, interrupting the concurrent kernel
build too. Cleanup tried external umount before unregistering and failed.
The user rebooted the Build VM; native execution recovered and the registration
was gone. No target deployment or target storage writes occurred.

The correction emits textual hex escapes, tests the full architecture mask
against native/interpreter ELF headers, unregisters using a shell builtin
before external cleanup, and runs the builder in a separate user namespace
with its own binfmt_misc instance. Tests and a container isolation smoke test
must pass before retrying package installation. Failed logs are retained in
`out/ubuntu/rootfs-build.log` and `out/ubuntu/kernel-build.log`.

## Initial qualification plan

The bridge now has a dedicated lab key outside Git; only its public half was
supplied to the builder. At this checkpoint, M7-A through M7-E were not
passed. Acceptance requires systemd multi-user, serial getty, Ethernet/SSH,
retained MMC/UVC/UDC and all frozen gadget modes, and 20 consecutive clean
software reboot cycles with bridge-side and target-side evidence. Stage with
two bring-up boots, five after fixes, then the final 20. No tag or push until
all gates pass. Read-only/overlay and persistent-data design remain later gates.

## Builder recovery and first Ubuntu hardware result

The isolated namespace smoke test passed. The initial isolated build rejected
an unnecessary sysfs bind; a later apt attempt rejected the default CA lookup
in the minimal base. Both failed trees/logs were preserved. Leaving sysfs empty
for package installation and explicitly setting apt's public CA-bundle path
allowed the pinned package installation to complete with TLS/signature checking.
53 local tests passed, including architecture-mask and raw-NUL regression tests.

Finalization was repeated with identical tarball SHA-256
`d4a66514d3e2bf27a6574f0aab8f990a3172bf1ab55adb83bed416badf9d87ce`
and cpio/gzip SHA-256
`810c8164d4057b8592a3a0893a63a5af4fea03a4a5ee4954289afae2d4202c5d`.
This verifies finalization repeatability, not yet two fresh package builds.

Hardware run `20260906T073522Z-unknown-247750` booted Ubuntu systemd 259.5 as
PID 1 using the M7 config exception and unchanged M5 DTB. **FAILED:** missing
CONFIG_PROC_SYSCTL prevented journald from reading `/proc/sys/kernel/hostname`
and udev from setting up its `/proc/sys/kernel/domainname` namespace. Missing
CONFIG_FILE_LOCKING also produced ENOSYS for console locking. Getty device
activation and network-online timed out. The later multi-user target message
does not qualify the system: essential units failed and Ethernet/SSH were
unreachable. The transferred source snapshot had no Git metadata, so the run
ID says `unknown`; `rootfs-manifest.json` records the actual Build VM source
commit, dirty state and per-file hashes.

Serial BREAK + SysRq b produced no target response in recovery run
`20260906T074021Z-unknown-887794`. It is failed, not a clean reboot pass.
Both completed runs were archived via SFTP to
`out/ubuntu/first-failure-evidence.tar.gz`, SHA-256
`e02ce5fbe78e7af4cc0a93617e7f0511d8eed6b0591b5a5078a85cd8e19688c2`.
No SD writes or permanent U-Boot changes occurred.

The corrected M7 exception adds PROC_SYSCTL, FILE_LOCKING, and the autofs
filesystem requested by PID 1. Explicit locale/keymap/UTC configuration is
included in the rootfs. The new Image hash is
`5337307fe1b5bb8c2d5417ef3a2f7b0facc81dcb0144cfd42a47948810c95d42`;
the staged 61,569,640-byte initramfs hash is
`63d0a3379c8e8942d6000e8704d3020da33e1df0cc6c4c8fd6447559b4096819`.
The user power-cycled the target after the failed boot. The UART adapter
re-enumerated; the first recovery watcher held its old file descriptor and
missed that boot. The recovery helper now reopens the stable UART path on
hangup. Vendor SD boot was recovered using the existing external credential;
subsequent target transitions use clean software reboot through vendor U-Boot.

Run `20260906T075214Z-unknown-420149` reached a usable Ubuntu console but failed
automation: the serial parser greedily swallowed output between systemd 259
OSC progress markers. A non-greedy parser correction and a regression test
preserve the command markers. Run `20260906T075451Z-unknown-778829` then passed
PID 1 systemd, multi-user/getty, zero failed units, exact Ethernet/no default
route, bridge ping, and UART-pinned host-key SSH authentication.

Hardware run `20260906T075835Z-unknown-086280` passed MMC (block-device read-only
plus ext4 ro,noload), EMAC1, EHCI1/MS2131, native V4L2 enumeration, USB0 UDC,
keyboard/absolute/relative HID reports, unbind/rebind, and read-only mass storage
including rejected filesystem and SCSI writes. Concurrent capture produced
60 non-empty distinct frames, 59 transitions, 36,864,000 bytes, zero startup
or stream errors, and nine concurrent full storage-image reads. Host/target
USB logs had no unexpected errors. These are provisional passes on the image
above; repeat the checks on the final reproducible payload before acceptance.

The final rootfs includes local systemd presets because an uninitialized
machine-id causes first boot to reapply package defaults. These keep ssh.socket,
systemd-resolved and unnecessary maintenance timers disabled while enabling
networkd, serial getty, SSH and first-boot host-key generation. DNS remains
unconfigured and unnecessary. The final fresh-build and reboot gates were pending at that checkpoint.


## Final reproducible payload

Two fresh Ubuntu Base extractions and pinned package installations, finalized
with the same inputs, produced identical bytes. The comparison and access-policy
checks are in `out/ubuntu/reproducibility.json`.

| Artifact | SHA-256 |
| --- | --- |
| Image | `5337307fe1b5bb8c2d5417ef3a2f7b0facc81dcb0144cfd42a47948810c95d42` |
| unchanged DTB | `3dadd0efd2c9ded33d852446a32e9cd2de2a6989c1f01798c1ab3c6f49887ee2` |
| rootfs tar | `27fbfd4a8cf34325c9804efa8d344196732d2956709577c3374819523ec60794` |
| RAM cpio/gzip | `8bde88f7e26ee5a040f6c4771e1b2a7bf4828f0e0597065f731b8129233ce675` |
| package inventory | `70d97902d3167a1bf747482e3244b82543d5221807450d17bc41719e2f80e60e` |

The 61,566,567-byte RAM image fits the unchanged 64 MiB transport window.
The archive contains an uninitialized machine-id, no SSH host keys, locked
root/user passwords, and only the externally supplied lab public key. The
builder rejects private-key input before mounting it into a container.

Final-image bring-up boots `20260906T080622Z-unknown-481042` and
`20260906T080712Z-unknown-369580` passed all M7-B/C checks including the local
service presets. The independent reboot auditor verified distinct boot IDs,
systemd shutdown/reboot before vendor U-Boot, unchanged artifacts, and the
uninterrupted boot chain.

Hardware run `20260906T080833Z-unknown-502732` passed on that exact payload:
60 non-empty frames, three unique hashes, ten changes, zero startup/stream
errors. A separate bridge test-source process had failed display negotiation,
so a repeat with the known moving pattern was requested. A same-boot rerun
`20260906T081024Z-unknown-651856` failed the frozen helper's existing-gadget
guard; use a fresh boot for every complete hardware run. Fresh boot
`20260906T081136Z-unknown-809228` passed M7-B/C, but hardware run
`20260906T081228Z-unknown-097882` failed the stricter M7 gate on one initial
partial-frame discard. Its subsequent 60 frames were all distinct and had
zero stream errors; dmesg had no UVC/USB error. This known startup condition
is retained as a negative result, not silently excluded or relabeled passed.


The five-boot staging gate passed with an independently audited clean chain.
The next hardware run `20260906T081826Z-unknown-681193` again reported exactly
one initial short buffer (2,242 bytes, sequence 0), followed by 60 distinct
614,400-byte frames without errors. The prior startup discard was 3,697 bytes.
Both attempts remain failed under the M7 wrapper's strict zero-startup-error
rule. No driver/config/gadget change was made to conceal the startup condition.


Fresh boot `20260906T081931Z-unknown-733870` passed M7-B/C. Its complete hardware
run `20260906T082022Z-unknown-531318` passed the strict gate: 60 non-empty frames,
60 unique hashes, 59 changes, 36,864,000 bytes, zero startup/stream errors, and
concurrent verified HID/storage activity with no USB errors. The final
20-consecutive-clean-reboot acceptance run starts from this qualified boot.
The occasional initial partial-frame behavior remains documented above; the
accepted bounded capture does not imply every stream start is free of pre-roll.


## Rejected first 20-boot batch: early readiness snapshot

All 20 initial runner invocations returned a pass, but the independent audit
rejected the batch. Run `20260906T083729Z-unknown-122990` sampled multi-user
as inactive and systemd as starting while SSH host keys were still generating.
SSH subsequently authenticated and reported multi-user active, but the earlier
snapshot did not meet the settled-state requirement. `systemctl is-active`
with two units returns success when either is active; serial getty alone had
satisfied that check. The original reports remain immutable and a separate
`rejected-twenty-audit.json` marks the batch unqualified.

The runner now waits on `systemctl is-system-running --wait`, checks multi-user
and serial getty separately, and checks running state again through authenticated
SSH. The auditor also explicitly requires `State: running`. The local suite has
58 passing tests, including rejection of an early status snapshot. No payload
or kernel change was made. A new full 20-boot sequence was required; its accepted result follows.


## Acceptance

M7-A through M7-E passed. The corrected final sequence contains 20 consecutive
clean software reboot cycles, with distinct boot IDs and no omitted or intervening
boot attempt. Each cycle captures systemd shutdown, vendor U-Boot, exact TFTP
artifact sizes, PID 1 systemd, settled running state, multi-user and serial getty,
zero failed units, the static lab network, and UART-pinned SSH key authentication.
The first run is `20260906T084050Z-unknown-168419`; the last is `20260906T085704Z-unknown-990235`, finished `2026-09-06T08:57:54.135111+00:00`.
The 2- and 5-boot staging gates also pass the strengthened independent audit.

The complete hardware pass is `20260906T082022Z-unknown-531318`: MMC read-only,
EMAC1, EHCI1/MS2131, V4L2, USB0 UDC, all three HID modes, rebind, read-only
mass storage including write rejection, and concurrent bounded changing capture
with zero startup/stream errors. Earlier partial-frame attempts and the rejected
first reboot batch remain explicitly recorded; acceptance does not erase them.

Selected machine-readable results are in [M7 evidence](evidence/m7-ubuntu-rootfs.json).
The full immutable run archive is `out/ubuntu/m7-evidence.tar.gz`, SHA-256
`b33e92cfc2b4ea8952a3ea2b97dc35e56f1482930207371fd13f94c2dddb3c9e` (6991040 bytes). It includes UART/U-Boot logs,
unit state, journals, network/ethtool, effective sshd policy, authenticated SSH
output, OS/kernel/build identities, gadget/host descriptors and capture results.
The [package inventory](evidence/m7-rootfs/packages.tsv),
[build manifest](evidence/m7-rootfs/build-manifest.json), Canonical signature
status and kernel config delta are retained alongside the summary. The original
build manifest's `not_qualified` field is the pre-HIL build state; the independent
acceptance record above is authoritative for qualification. A separate reviewed
source manifest records the final verifier sources without changing the payload.
58 local tests pass, including the OSC parser, emulation registration and reboot
acceptance-audit regression tests.

### Write scope and retained recovery

Build writes occurred on the AMD64 VM under `out/ubuntu/` and in its container
cache; Linux compilation reused the persistent object directory and wrote separate
M7 outputs. The bridge received VM-built files under `/home/user/blikvm-m7-transfer/`
and `/home/user/blikvm-m7/artifacts-final/`, published the three boot files under
`/srv/tftp/m7/8bde88f7e26ee5a040f6/`, and stored evidence under
`/home/user/blikvm-m7/runs/`. Ubuntu ran entirely in writable RAM, including
machine-id, host keys, journal and gadget backing data. MMC tests set the block
devices read-only and used ext4 `ro,noload`. No recovery-SD flashing, partition
change, bootloader replacement or persistent U-Boot environment write occurred.

The accepted tag is `ubuntu-26.04.1-rootfs-baseline`. M6 remains **DEFERRED,
not passed**. Persistent-data partition design and final read-only/overlay policy
remain separate later gates. No kvmd, nginx/web UI, GPIO/ATX, LCD/fan/buzzer or
Wi-Fi/Bluetooth work was started. The proposed next slice is a pinned uStreamer
package and a bounded service-level video smoke test on this baseline, before
kvmd integration.
