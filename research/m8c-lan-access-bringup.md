# M8-C — controlled LAN HTTPS and client capacity

**PASSED — 2026-09-07.** Restricted direct HTTPS, normal certificate trust, upstream authentication, lifecycle recovery and five consecutive clean boots passed. Two simultaneous authenticated video clients are qualified for the tested 1080p30 workload. Release tag: `ubuntu-26.04.1-kvmd-lan-baseline`.

Baseline: `ubuntu-26.04.1-kvmd-web-baseline` (`aa8e6a3`). M6 GPIO/ATX remains deferred.

## C1 — qualified network path

Bridge `user-0`, development source `192.168.88.1` on `enp1s0`, connects directly to target `eth0` at `192.168.88.2:443`. The bridge resolves `blikvm-v4.lab` through an explicit hosts entry. HTTPS/video does not traverse an SSH tunnel. SSH remains the separate hardware-control/evidence transport.

The target uses one explicit IPv4 HTTPS listener. No wildcard, IPv6 or HTTP listener is configured. A target nftables input policy allows HTTPS only from the intended bridge source on eth0; all other HTTPS and all HTTP traffic are dropped. SSH and ICMP remain available to the bridge; forwarding defaults to drop. IPv6 remains disabled in the kernel.

The M8-B kernel had no Netfilter. The M8-C additive kernel configuration enables only the required nftables IPv4 path and dependencies. No USB/UVC driver source, device tree, gadget descriptor, storage backing image, kvmd or uStreamer package is changed. nftables and three missing libraries are installed from the inherited locked Ubuntu snapshot. nginx requires the firewall service and verifies its table at each startup. Reload replaces only the owned table atomically; stopping the firewall unit retains the rules.

## C2/C3 — trust and authenticated Web UI

A dedicated RSA-3072 development CA signs a 30-day server certificate for DNS `blikvm-v4.lab` and IP `192.168.88.2`. The CA private key remains on the Build VM. The server key and htpasswd enrollment are in the ignored private RAM image; the explicitly approved SFTP transfer installs that image on the existing isolated bridge/TFTP path. Public evidence contains only certificates, metadata, fingerprints and the generation script.

Chromium uses its normally trusted bridge-user NSS database. The Playwright HTTP client uses NODE_EXTRA_CA_CERTS for the same public CA. No insecure-certificate flags or ignoreHTTPSErrors bypass are used. Independent TLS 1.2 and TLS 1.3 handshakes verify the DNS and IP identities, chain, fingerprint and validity period. Untrusted and wrong-name handshakes fail; Chromium separately rejects the wrong-name certificate.

Upstream kvmd authentication remains mandatory. Browser tests cover invalid/valid login, logout and denial afterward, authenticated API/WebSocket, actual UI rendering/reload, moving video, service restart reauthentication and HDMI loss/restoration. HID/MSD/ATX/GPIO routes remain absent (404); hardware-control UI transports remain disabled in the frozen package.

## C4/C5 — performance and capacity

The native gate delivered 29.83 fps. The direct browser gate delivered 29.92 fps. The corrected resource-instrumented one-client gate delivered 29.91 fps. Device mode remains MJPEG 1920x1080, exact interval 30/1, native quality 0, with one kvmd-owned uStreamer.

| Two-client trial | Client | Frames | Delivered fps | Bytes | Unique hashes | Max gap (s) |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| 1 | 1 | 3590 | 29.910 | 148921702 | 3583 | 0.135719 |
| 1 | 2 | 3591 | 29.919 | 148963182 | 3584 | 0.101281 |
| 2 | 1 | 3578 | 29.814 | 148423653 | 3577 | 0.115128 |
| 2 | 2 | 3579 | 29.822 | 148465146 | 3578 | 0.115217 |
| 3 | 1 | 3591 | 29.919 | 148963165 | 3591 | 0.129704 |
| 3 | 2 | 3591 | 29.919 | 148963165 | 3591 | 0.131433 |

Each pair uses two independent processes and separate authenticated sessions on the bridge, with both MJPEG connections active concurrently. Raw per-frame timestamps, byte counts, SHA-256 hashes, changing windows, and reconnect streams are archived. The unchanged gate is at least 3,240 frames and 27 delivered fps per client over 120 seconds, with the existing 3-second maximum gap. No threshold or capture quality was lowered.

This qualification uses the same deterministic 1080p30 moving-ball HDMI workload as M8-B. Native MJPEG bandwidth depends on source content. Capacity evidence covers two concurrent MJPEG transport clients and a separately qualified real browser; additional clients and higher-bitrate source workloads require their own qualification.

## Failures retained

The initial nginx startup check failed because inherited address-family restrictions blocked Netlink; the corrected drop-in permits AF_NETLINK. A provisional full HIL run recorded one UVC URB resubmission error during repeated stop/start and remains failed. The fresh corrected-image full HIL passed all repeated restarts, three HDMI cycles and host-side frozen gadget checks without USB/UVC errors. Missing source transfers and the initial process-name resource-sampler omission were corrected and retained as harness failures. Resource sampling now identifies uStreamer by executable path; the single-client resource gate was repeated.

## Controller interruption during boot 4

The long-running bridge controller was interrupted after approximately thirty
minutes and its named background session disappeared. Boot 4 itself had already
passed startup access checks. Its HIL child completed all checks and wrote a
passing immutable `test-results.json`, then received BrokenPipeError while
printing to the absent controller. The same target boot ID and healthy services
were verified read-only. `lan-series-resume.py` recovers that exact recorded
result, retains the interruption logs, finishes boot 4's browser/capacity gates
and then performs boot 5. No extra reboot or service repair is used. The independent five-boot audit passed, including exact equality
between every series summary and its immutable run result.

## Certificate record and access evidence

The leaf is valid from **2026-09-06 23:09:34 UTC** through **2026-10-06 23:09:34 UTC**. Verification used the bridge's current UTC clock. SHA-256 DER fingerprint:

```text
2A:36:0C:40:10:ED:32:50:25:4E:C5:A2:43:E6:FC:FE:B3:91:27:B6:67:1E:86:61:E4:F7:F7:43:7A:CB:AA:B2
```

[Public leaf](evidence/m8c-lan/server.crt), [public CA](evidence/m8c-lan/ca.crt), [subject/SAN/expiration](evidence/m8c-lan/server-certificate.log), and [generation procedure](../build/kvmd-lan/README.md) are retained. Renew and requalify trust before expiration; this is a development certificate.

Independent nginx effective configuration, `ss`, `/proc/net/tcp*`, and remote probes agree: HTTPS listens only on `192.168.88.2:443`, SSH only on `192.168.88.2:22`, with no port 80 or wildcard listener. A temporary unauthorized source `192.168.88.99/32` on the same lab Ethernet could not connect; target firewall drop counters increased. The alias was removed afterward. A target loopback attempt to the LAN HTTPS address was also denied. This verifies source and interface filtering independently of the nginx binding. Effective rules and listener inventories are [archived](evidence/m8c-lan/).

## Resource comparison

M8-B's accepted HTTPS preflight delivered 29.73 fps; M8-C delivered 29.92 fps. M8-B's failed two-client 3,237-frame / 26.97-fps diagnostic remains failed and unchanged in its original evidence. No broad performance rewrite was needed: nginx proxying/buffering and uStreamer fan-out implementation are unchanged. The direct transport passes; this alone does not establish the cause of the older tunneled result.

The corrected single-client resource run used 2.35% of total target CPU; kvmd used 0.50%, uStreamer 2.73%, and the nginx worker 3.37% of one core. kvmd RSS was 58,140 KiB, uStreamer 30,168 KiB, nginx worker 9,260 KiB and master 9,692 KiB. Ethernet transmitted about 10.20 Mbit/s. The first pair used 2.46% of total target CPU, a 5.53%-of-one-core nginx worker, and about 20.33 Mbit/s Ethernet transmit. Per-trial CPU, RSS, Ethernet counters, TCP retransmissions/errors and streamer client counts are retained in [resource summaries](evidence/m8c-lan/resources/).

The archived M8-B native single-client reference recorded 3.92% of one core for the kvmd service, kvmd RSS 57,572–58,084 KiB and uStreamer RSS 29,884–30,300 KiB. M8-C's small RSS change is documented; M8-B did not separately sample nginx or whole-target CPU, so those values are not an exact paired comparison. Accepted capacity trials recorded no Ethernet packet errors/drops. Streamer state independently confirms two active clients during each pair. Each client also passes authenticated reconnect and changing-frame checks.

## C6/C7 — lifecycle and frozen regressions

Full native preflight and direct browser tests passed nginx restart, kvmd restart, authenticated reconnect, browser recovery and real HDMI DPMS loss/restoration. Three native HDMI cycles passed. Final inventories verify one kvmd-owned uStreamer, no stale Unix sockets or orphan process, correct authentication/certificate, and unchanged firewall policy after service restart. Accepted runs have no persistent nginx/kvmd/uStreamer/UVC/USB errors.

Ubuntu systemd health, Ethernet/SSH, MS2131/UVC, host-observed keyboard, absolute mouse, relative mouse and read-only MSD checks pass, including concurrent UVC regression. These use retained M5/M7 test paths; kvmd hardware-control APIs remain disabled. A byte comparison checks 421 frozen runtime files, permitting only the intended nginx identity/listen edit. kvmd `4.213-1blikvm2`, uStreamer `6.65-1blikvm2`, `/dev/kvmd-video`, MJPEG 1920x1080, exact 30/1 V4L2 interval, native quality 0, all gadget descriptors and storage semantics remain unchanged.

## C8 — five consecutive clean boots

Each boot restores the same image, firewall and explicit listener automatically; verifies normal TLS identity/trust, authentication, API/WebSocket, one streamer, exact capture mode and retained host-side M5/M7 regressions; and passes separate 120-second single and two-client measurements.

| Boot | Boot ID | Single fps | Pair client 1 fps | Pair client 2 fps |
| --- | --- | ---: | ---: | ---: |
| 1 | `210c76a7-7ba4-44d0-860a-82feb18caa5d` | 29.916 | 29.786 | 29.786 |
| 2 | `aac96dd2-1ec2-446c-851a-eaa56490e414` | 29.914 | 29.788 | 29.788 |
| 3 | `0bb32368-d413-4be0-8c7b-1b38516823d7` | 29.788 | 29.916 | 29.916 |
| 4 | `4840a8ef-eda4-49fa-81ef-0806e64f1500` | 29.792 | 29.908 | 29.909 |
| 5 | `44377e9f-7a87-4874-a053-93200d6e8430` | 29.917 | 29.785 | 29.785 |

All sixteen client measurements across the three preflight pairs and five boot pairs passed at 29.785–29.919 fps. Maximum pair inter-frame gap was 0.136536 seconds, below the unchanged 3-second bound. [Machine-readable replay](evidence/m8c-lan.json) includes each client's frames, bytes, hashes, gaps and exact fps. [Five-boot audit](evidence/m8c-lan/five-boot-gate.json) passed.

## Reproduction and evidence

See [build/enrollment workflow](../build/kvmd-lan/README.md). Two fresh public builds reproduce all five artifacts byte-for-byte. [Frozen comparison](evidence/m8c-lan/frozen-final-comparison.json), [artifact manifest](evidence/m8c-lan/build-manifest.json), [kernel configuration delta](evidence/m8c-lan/kernel-config-delta.txt) and [automation hashes](evidence/m8c-lan/automation-sha256.json) identify the exact tested candidate. Build-time manifests intentionally say not qualified; this report and replay record the later qualification. The runs originate from `aa8e6a3` with the archived M8-C working changes, not a claim that those changes existed in that parent commit.

The private enrolled RAM image is 89,035,970 bytes, SHA-256 `b9617300a246a20aa7d58d74a878f586bc03abeabed83bd66a16c1e48fc7d93e`. Public rootfs SHA-256 is `c79135fa661968323137d2618f035988d20d37c978f9517c504199d15c616ad1`; public initramfs SHA-256 is `2abe4b663aa016501460c40443b52b62d605da6c0599651870bd66f44d98a8da`.

The complete non-secret evidence archive contains 1,355 files (UART/U-Boot, target/host USB logs, raw frame measurements, resource samples, source snapshots, passing and failed runs). It is retained on the bridge at `/home/user/blikvm-lan/m8c-evidence.tar.gz` and the VM at `out/kvmd-lan/m8c-evidence.tar.gz`, 7,669,071 bytes, SHA-256 `38c5c62a22064221b32f232f8680d4f416643ed0707879d18c06eee7169a4b6b`. Authenticated SFTP download matched this hash. Selected public evidence is committed under [evidence/m8c-lan](evidence/m8c-lan/); private keys, credentials, cookies and enrolled images are excluded. The public archive passed an exact secret-material scan. Selected text logs trim trailing whitespace; the full archive preserves original bytes. The committed inventory helper removes one trailing space from its tested source, without a logic change.

Local validation: 78 unit tests, Python/JavaScript/shell syntax checks, frozen runtime/package comparison, atomic nftables load/reload, reproducible public artifacts, and full offline replay of raw HIL evidence. No threshold was lowered and failed evidence was retained.

## Next slice — proposed M8-D, not started

Integrate kvmd keyboard plus absolute/relative mouse control, preserving the accepted gadget reports and descriptors. Qualify authenticated authorization, real host events, mode switching, reconnect/restart/reboot behavior and simultaneous video/access-policy regressions. Keep kvmd MSD and ATX control disabled. M6 GPIO/ATX remains explicitly deferred; Janus/H.264/VNC/IPMI and final read-only-root layout are outside this slice.
