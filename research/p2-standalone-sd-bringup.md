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
