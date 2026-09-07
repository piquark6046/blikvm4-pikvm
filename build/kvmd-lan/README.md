# M8-C — qualified controlled LAN HTTPS

Accepted at `ubuntu-26.04.1-kvmd-lan-baseline`. See the [qualification report](../../research/m8c-lan-access-bringup.md). M6 remains deferred; kvmd hardware control is disabled.

The image binds only `192.168.88.2:443`, with `blikvm-v4.lab` as the lab
certificate hostname and the exact IP as an additional SAN. Only bridge
`192.168.88.1` arriving on target `eth0` is authorized. HTTP is dropped.
The input and forwarding policies default to drop; the existing bridge SSH,
isolated ICMP, and non-web loopback traffic are retained. IPv6 stays disabled
in the kernel. Network filtering and upstream kvmd authentication are both
required. nginx requires the firewall service and checks its table at startup.
The firewall remains loaded when its service stops.

The frozen M8-B kernel lacks Netfilter. `linux-firewall.config` enables the
minimal nftables IPv4 path, using the existing incremental object directory.
Accepted kernel/DTB artifacts are not overwritten. The candidate rootfs starts
from M8-B public rootfs SHA-256
`3a40cafa3e690a0317a176d6bd9e5f2f2b96ce771514518d2cde69cdd2836347`.
Only nftables and its three missing libraries are added from the inherited
Ubuntu snapshot; their versions are locked. kvmd `4.213-1blikvm2`, uStreamer
`6.65-1blikvm2`, gadget files and video configuration are retained.

Build on the VM, sequentially:

```sh
bash build/kvmd-lan/build-kernel.sh
bash build/kvmd-lan/build.sh
python3 build/kvmd-lan/check-candidate.py
python3 -m unittest discover -s tests
```

The rootfs build requires a fresh `out/kvmd-lan/rootfs` directory. Preserve
previous build trees and logs by renaming them before an additional build.
Never clean the persistent kernel build directory. The first local rootfs
attempt failed because the copied shell script lacked an executable bit;
the wrapper now invokes it with `bash`. The first kernel build omitted the
separate `NF_TABLES_IPV4` selection; the final candidate includes it. Neither
attempt was deployed. Their logs remain under `out/kvmd-lan/`.

`provision.py` creates a dedicated RSA-3072 development CA (365 days) and a
30-day server certificate with serverAuth EKU and exact DNS/IP SANs. It reuses
the private M8-B test credential and SSH enrollment and writes a separate
private cpio layer and enrolled RAM image. Generation does not change M8-B.
Keep this entire directory ignored/private; never archive credentials, either
private key, browser cookies, or the enrolled image as public evidence.
The CA private key stays on the Build VM. Transfer to the bridge requires only
the test credential, public CA/server certificates, and enrolled image.

```sh
python3 build/kvmd-lan/provision.py \
  --private-dir out/kvmd-lan/private \
  --previous-private out/kvmd-web/private \
  --artifacts out/kvmd-lan/artifacts
```

The direct browser harness is `lab/lan-browser.mjs`. It uses normal browser
certificate verification (`ignoreHTTPSErrors:false`), verifies the leaf
fingerprint, and measures direct HTTPS. Before execution, resolve
`blikvm-v4.lab` to `192.168.88.2` on the bridge and explicitly enroll the public
CA in the bridge user's NSS trust database. The user approved enrollment transfer to the configured bridge, and the
public CA has been enrolled there. The pinned Playwright/Chromium runtime and its OS prerequisites
have been prepared on the bridge, without target changes.

## Private deployment material

The private locations are:

- `/home/user/blikvm-lan/private/credentials.json` (private test login)
- `/home/user/blikvm-lan/artifacts-final/initramfs.cpio.gz` (private RAM image)

The enrolled image contains the target's server private key and htpasswd
entry and must be kept private on the bridge and served only through the
existing isolated RAM/TFTP path. It is 89,035,970 bytes, SHA-256
`b9617300a246a20aa7d58d74a878f586bc03abeabed83bd66a16c1e48fc7d93e`.
The CA private key is not part of that image or the bridge transfer.

The accepted public artifacts reproduce byte-for-byte in two fresh builds.
The complete report links the five-boot audit, raw evidence archive hash,
per-client metrics, resource summaries and retained failures. Run the full
native preflight with `lab/lan-preflight.py`, then the five-boot sequence with
`lab/lan-series.py` on the bridge after staging the public lab helpers and private
artifacts. These scripts operate from the bridge's `/home/user/blikvm-lan` tree.
Use authenticated SFTP to export evidence, then replay on the VM:

```sh
python3 lab/lan-acceptance-gate.py --root out/kvmd-lan/evidence-bridge \
  --certificate out/kvmd-lan/private/server.crt
```

`write-manifest.py` hashes public artifacts and, when enrollment exists,
creates a new private artifact directory named by its image hash. Existing
private artifact directories are never overwritten. New builds start with a
not-qualified manifest; qualification is a separate hardware evidence step.

References: [nftables atomic scripting](https://wiki.nftables.org/wiki-nftables/index.php/Scripting)
and [nftables rule semantics](https://netfilter.org/projects/nftables/manpage.html).

## Preserved provisional failures

The first hardware boot loaded the firewall but nginx could not start: its
inherited `RestrictAddressFamilies` blocked the new nft Netlink check. The
corrected drop-in permits AF_NETLINK and retains the inherited restrictions.
The first rootfs and failed boot remain archived. The corrected image uses
a distinct private artifact directory and hash. Missing HIL source-dependency
transfers and a rejected multiline SSH-MCP command were corrected in the harness.

A provisional full native HIL run saw one `uvcvideo ... Failed to resubmit
video URB (-1)` during repeated stop/start. That run is failed, not accepted;
its complete evidence is retained. In the pinned kernel, an URB being killed
can cause `usb_hcd_link_urb_to_ep` to return `-EPERM`, and the UVC asynchronous
copy worker logs failed resubmission. This is a possible shutdown-race
explanation, not a proven diagnosis or a reason to suppress the error. A fresh
full HIL run on the corrected image and five subsequent boots passed without
this error. The failed run remains failed and is retained in the archive.


Public CA trust on the bridge (run as its development user):

```sh
certutil -A -d sql:$HOME/.pki/nssdb -n 'BliKVM M8-C Development CA' -t 'C,,' -i /home/user/blikvm-lan/private/ca.crt
```

Resolve `blikvm-v4.lab` to `192.168.88.2` and use the pinned browser runtime.
`lan-session.py` supplies the public CA through `NODE_EXTRA_CA_CERTS` for
Playwright's HTTP client. Chromium verifies through its NSS trust database.
The accepted leaf expires 2026-10-06 23:09:34 UTC; renew and repeat identity/trust
qualification before expiration. Never use insecure-certificate bypass flags.
