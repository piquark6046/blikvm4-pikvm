# P2 standalone SD bring-up

## Attempt 01 — FAILED, permanently preserved

Attempt 01 failed the automatic SSH recovery gate after a cold standalone SD
boot with Ethernet disconnected. It must never be resumed or credited as a
passing qualification. P1 remains historically offline-passed; this hardware
failure does not retroactively fail P1. No baseline tag is created.

### Failure chronology (2026-09-12 UTC)

The expendable SD was written from P1 commit `711dbb6`. Earlier connected-boot
checks do not replace the disconnected-boot gate. A first interrupted UART
capture and failed harness observations are retained in the private archive.
At approximately 12:25, the standalone boot with Ethernet physically disconnected
loaded the SD boot script, accepted Linux and SD root and reached Ubuntu login.
The bridge reported no carrier through 12:28:38. Missing UART service markers
are not proof that systemd failed to reach multi-user startup.

After physical Ethernet reconnection, the expected target answered ICMP.
At 12:31:18, TCP 443 connected while TCP 22 returned ECONNREFUSED (111).
At 12:32:07, HTTPS returned HTTP 302 with normal lab CA and hostname validation
(`ssl_verify_result=0`). SSH continued refusing connections. The live journal
could not be obtained; its volatile contents were lost at poweroff. The
restricted SSH bind/address-ordering explanation remains a hypothesis pending
exact offline configuration review and separate diagnostic runtime evidence.

No image/configuration modification or service repair followed the failure.
The user reports the target was powered off, the untouched recovery SD restored,
and the target later powered on with that recovery image. This restoration is
operator-reported; the current recovery system was not contacted for this record.

### Public artifact and sanitized medium identity

Original public raw image (1,077,936,128 bytes):
`873845575255879c13dc5a91aebfdbe269929e2af58b3a71c547661776e3c127`.
Original public zstd image:
`80da597e67074fbd55dd4f1ac41f6af63d268e06932c8e59c92005f45bbdf21e`.
Private enrolled-image SHA-256:
`befbede0b28ca46ec396a6e61d60ac31d99d5c9c6b3f802e213babaa926bcd05`.
Private enrolled receipt SHA-256:
`fbb7aea032f1daae15379a7d262617dc8bc16f611e5636dba44ea160831a15af`.
These identify the historical attempt, not a future R1 candidate.

The operator positively identified an expendable SD in a Generic SD/MMC USB
reader, capacity 15,634,268,160 bytes. The USB reader identity is not an SD CID;
exact reader identifiers remain private. Recovery and bridge system media were
excluded. Write, fsync and flush completed. The original unaligned direct-read
failure remains retained. A page-aligned O_DIRECT reader then compared all
1,077,936,128 written bytes with the enrolled image. After physical removal and
reinsertion (diskseq 25 -> 28), the complete direct comparison and SHA-256 passed
again. Read-only fsck passed; partition layout, UUID and PARTUUID matched P1.

### Evidence preservation

[Machine-readable preservation receipt](evidence/p2/attempt01/preservation.json)
records independently recomputed UART, network evidence, enrollment receipt and
private archive hashes. Every hash referenced by the original failure record
was checked against the preserved local file. Consolidated private archive:
`8159c7c1c55f4f4573dc484fef0089a5efcaee278882cad606b0930dc7757256`.
Original archives and source records remain unchanged, including their historical
pending-restoration state. The new chronology above adds the operator's later
restoration report without rewriting those records. Raw enrollment, keys,
receipts and sensitive logs remain outside Git/public artifacts.

## Authorized next slice — P2-R1

Review exact installed configuration offline, then prepare Candidate 1 with
only `ConfigureWithoutCarrier=yes` in standalone networkd configuration.
Keep `ListenAddress 192.168.88.2`, no DHCP/default gateway/DNS/firewall expansion,
and no SSH restart override. Require fresh independent A/B public assemblies,
full offline gates and a new four-file private enrollment receipt. A narrow
cold-offline diagnostic and one carrier cycle must pass before freezing the
candidate and fresh-flashing P2 attempt 02 from zero. Diagnostic evidence gives
no qualification credit. Candidate 2 is conditional on preserved Candidate-1
failure demonstrating absent-address SSH startup.

Run 02 remains FAILED; Run 03 remains unaccepted history; Run 04 remains the
accepted core-KVM soak. P3, M6/ATX and RO/overlay work remain deferred.

[P2-R1 offline findings and Candidate-1 artifacts](p2-r1-offline-ssh-recovery.md)
record the subsequent separate revision; this does not change attempt 01.

## Attempt 02 — in progress, not accepted (2026-09-13)

Candidate 1 was frozen at `5ec62b3`. A fresh, explicitly confirmed expendable-SD
write, fsync, flush and complete direct readback passed. Physical reinsertion
was followed by another complete direct comparison, raw SPL/FIT checks and
read-only fsck. Private enrolled-image identity is
`c261a2328594bca90f6a47bc566429a5684c0bf573de0d4089f2843f114eae24`.
Write archive SHA-256:
`051d990253e019c63c042e3050fe668d8d0d04cc23085be5a0a0809ee4902a56`;
post-reinsert archive:
`7e2c758e6eeb428e5916bd73207ea5837fbd4782125889eae9bf2a5fc1c9b755`.

Before the intended cold boot, passive UART unexpectedly showed an older running
system reporting ext4 errors. The operator confirmed power had remained connected
during card handling. Qualification paused without target repair. After physical
power removal, the expendable SD was independently read in full: every image byte
still matched the frozen enrolled image, both bootloader hashes matched, and
read-only fsck passed. No reflash or filesystem repair was performed. This
interrupted observation receives no qualification credit. Final incident archive:
`cb07082d99ca17b54fab173982372da164e8a1aed3c0b810a69bcc34dd75b583`;
read-only recheck archive:
`f56dcf2022881872cc3d372746570d13ed29e8e1d7424d1d848791a625a07bea`.

The subsequent coldboot01 began with UART absent and Ethernet carrier zero,
using the verified card inserted while physically unpowered. The operator later
explicitly approved extending the shared-power UART exception to P2: missing
cold-boot SPL/TF-A bytes remain an evidence gap; uninterrupted systemd-through-
recovery capture and a complete firmware trace on the normal reboot are required.
This approves qualification scope, not P2 acceptance. The earlier diagnostic-only
exception remains historical and does not itself grant P2 credit.

After more than five minutes offline following the login prompt, independent
probes were armed before Ethernet reconnection. Trusted HTTPS recovered in
2.089 seconds and enrolled SSH login in 3.721 seconds after observed carrier.
No reboot, UART command, configuration modification or SSH repair occurred.
The archived journal shows SSH listening on 192.168.88.2 at boot +126.927 seconds,
before first carrier at +887.117 seconds; NRestarts=0 and ip_nonlocal_bind=0.
SSH and HTTPS listen only on the approved address. ssh.socket is disabled and
inactive. The expected 120-second wait-online timeout is explicitly retained as
the sole failed unit, not reset or hidden. Journal allocation was 4 MiB.

The RW ext4 root is physical `/dev/mmcblk0p1`, with the frozen UUID/PARTUUID and
SD-root command line. All 10,686 selected frozen artifacts matched, including
boot, usr, opt, systemd, kvmd and SSH policy files. Private archive hashes:

- Disconnected-boot snapshot: `f2bd4cf8e0a41700e4b49993e4080bd21cf4480b07a05d59cd4919561d0d4a40`.
- Recovery/startup journal: `3eebf57dd64639ce821b85d8e646ad8087473d7363d4ace0fb91469771acf1f9`.
- SD identity/full journal/artifact comparison: `b76b7665507bd5e3363baba547e15d80a4e3156bad18696997646f6873a00c30`.

Browser/core qualification is still in progress. Two bridge harness failures are
preserved without credit: an obsolete card0 DRM path (the connected Intel HDMI
output is now card1-HDMI-A-2), and an overly restrictive controller umask that
prevented Chromium from reading a host acknowledgement. The latter reached
normal login and passed its initial RO MSD check before stopping. Isolated new
harness runs change only the bridge connector path and evidence-file group access;
no target production files or functional assertions are changed. Browser/video,
HID/MSD, physical reconnect, persistence, complete normal-reboot firmware capture,
post-reboot and second-cold-boot checks remain required. Attempt 01 remains FAILED;
P1 historical offline-pass and all deferred phase boundaries remain unchanged.

### Attempt 02 core progress — still not accepted

Fresh browser/MSD qualification passed all 11 stages. The combined two-client
120-second streams passed at 29.630 and 29.647 fps, with 12 HID cycles and
254 full direct RO-media reads. The browser/HID/MSD workload also passed,
including held-input cleanup and service lifecycle checks, with 304 direct reads.
All 2,177 member hashes in the private core archive were independently verified:
`db34f549ea7e85b964efec85566a08aa8ddf5faa07ed7ab0320aa48da25c27ca`.

LAN source filtering, normal TLS verification and helper privilege checks passed.
An additional bridge HDMI harness failure is preserved: its new online=false
assertion contradicted the accepted M8-A/M8-B contract, which explicitly says
MS2131 remains capture-online during HDMI absence. That run has no HDMI recovery
credit; archive SHA-256:
`bf786e278feee039dbb3f0aaf738974310d97232758a1086e00ad023fdf908a7`.
A fresh cycle applied the unchanged accepted behavioral contract: four identical
no-signal snapshots during verified held DPMS Off, then 446 distinct frames in
15 seconds after restoration, with the same uStreamer PID/start generation.
LAN/HDMI evidence and member hashes verified; archive SHA-256:
`4abf93c1886ebfeb2663f9776a9dd4aaa7f4e993636f2a698173d665f19252f9`.

Physical USB-PC reconnect monitoring is armed after successful descriptor,
RO-media and target inventory checks. Reconnect, persistence, reboot/full firmware
capture, post-reboot smoke and second standalone cold boot remain pending.

### Physical reconnect and normal reboot

Physical USB-PC removal was observed independently: gadget, all HID host objects,
and storage/SCSI objects disappeared while UART and Ethernet remained connected.
Reinsertion passed descriptor identity, complete RO-media reads/rejected writes,
HID API, real MSD browser and real HID browser regressions without target repair.
All 594 archive member hashes verified; private archive SHA-256:
`cff3503218d483f94eb201112895aab2dc38d60d33eecb6add0907b824ce712e`.

A 65,536-byte exclusive persistence file was written and fsynced on physical RW
SD root. The volatile pre-reboot journal was archived before normal systemd reboot.
With UART already open, the reboot captured SPL, TF-A/BL31, U-Boot, SD boot script,
Linux SD-root command line and systemd in order without UART disconnect. The
legacy TF-A AXP305/RSB probe error and FAT-environment message match the preserved
vendor boot evidence; see research/boot-chain.md and vendor-system/uboot.txt.
The new boot ID differs, while machine ID, all SSH host public-key hashes and
persistence-file content are unchanged. The connected reboot has no failed units.
Private normal-reboot archive SHA-256:
`65e68116534a5ba6fe6b3ba4f038c13739f0074bce42d242b9fc86043f93fbfc`.

[Independent progress replay](evidence/p2/attempt02/verify-progress.py) validates
archive/member hashes and completed core/reconnect/reboot gates; its
[sanitized result](evidence/p2/attempt02/progress.json) explicitly does not accept
P2. Post-reboot core tests, second cold boot, final review and persistence cleanup
remain pending.

Post-reboot core replay passed all three stages: the 11-stage MSD/browser test,
two-client/HID/RO-media workload (29.897 and 29.889 fps; 255 direct reads), and
browser/HID/RO-media workload (301 direct reads). All 2,129 private archive member
hashes verified; SHA-256:
`a8a2e3bc25b046d507ef043909c937ab37c6f99ef450ec3c8e3812bad90bb326`.
The persistence file still matched before shutdown, no units were failed, and
journal allocation remained 4 MiB with 24 KiB under /var/log. The guarded normal
poweroff was requested only after the full volatile journal was archived.
The second standalone cold boot and final qualification review remain pending.
