# VM / LattePanda migration sanity check

Date: 2026-09-06. Status: local builds passed, bridge setup restored, and the
VM-built baseline booted successfully. Migration fails the changing-frame
UVC check; the current HDMI input path needs confirmation. M5 has not started.

## Repository and retained baseline

The initial working tree was clean at
`8cd48fca415e22c1f34d865cd78cf57e4e9ee03c` (`main`), one commit ahead of
`origin/main` at `b70f798d6b38ef9244270551505fdc41add364a7`. Fetching all
remotes and tags succeeded. There are no local tags after fetch. The commit
named `linux-7.2.3-uvc-baseline` is `3e5782e`; it is a commit subject, not a
tag in this checkout. Historical hashes/tag names in the research documents
must not be assumed to be available refs in this migrated history.

`b70f798` contains the accepted UVC config, builder requirements, automation,
and tests. HEAD differs from it only by AGENTS.md. The checked-in
`initramfs/v4l2-test.c` and `research/uvc-v4l2-bringup.md` are present.
The recorded UVC evidence and hashes remain the comparison baseline.

`python3 -m unittest discover -s tests -v`: all 20 tests passed.

## Build VM inventory

The VM provides 12 CPUs, approximately 6.9 GiB RAM plus 4 GiB swap, Docker,
and 228 GiB free workspace storage. There was no `out/` directory and no
`artifacts/` directory before this check. No persistent Linux objects or old
raw run directories were migrated here.

Regenerate the pinned downloads, extracted/patched Linux source, toolchain
image, persistent `out/build/linux-7.2.3` objects, and current Image/DTB/config/
initramfs/manifest. The existing incremental builder is used with six jobs;
no clean/mrproper operation or build-directory deletion is needed. A first
build on an empty VM necessarily populates the missing cache. Old hardware
logs cannot be regenerated as historical evidence; new boots get new run IDs.
Missing vendor binary backups are not prerequisites for the upstream build.

## VM build results

Initial sandboxed build `20260906T015225Z-8cd48fc-392897` failed resolving
cdn.kernel.org. Retrying with authorized network/Docker access succeeded:
`20260906T015248Z-8cd48fc-277170`. Both downloads matched the checked-in pins;
the kernel build, board DT schema validation, static AArch64 utility build,
and initramfs validation passed. No build-input changes were made.

No-change incremental run `20260906T020041Z-8cd48fc-987449` passed in about
seven seconds and reproduced all four artifact hashes and sizes.

| Artifact | Size | SHA-256 |
|---|---:|---|
| Image | 6,221,832 | `d3ba8fef5a3807ec31e554e743d305312ab0f16e80100c0ca551c92d43c36f52` |
| DTB | 20,552 | `4b94e64517a3eb117e9aa4d9287334a72ba8e82bf448d4d05d08a5ec1ed1f3ef` |
| initramfs.cpio.gz | 4,297,578 | `9844fdfda62538a52074e66700610805c7486cc99afaab816044e96de9ee1218` |
| linux.config | 63,155 | `2231e384676b1567643b5f3cdd76900f6b702b1960c405a7e22e817184b88e39` |

The DTB and config match the historical UVC evidence exactly. Image and
initramfs hashes differ; Image has the same size, while initramfs is 81 bytes
larger. The cause is not established without the old artifacts. One known
reproducibility limitation is the unpinned KBUILD_BUILD_VERSION: this fresh
tree produces `#1 SMP PREEMPT 1970-01-01T00:00:00Z`. Toolchain packages are
installed from current Debian repositories despite the pinned base image.
Neither observation proves the cause of the differences. A new hardware boot
is still required; matching configuration is not a substitute for it.

The complete build evidence remains in the two successful out/runs
directories. `out/migration/uvc-baseline-deploy.tar.gz` contains a verified
Git bundle of HEAD and the incremental build run with artifacts, manifests,
hashes, and logs. Its transfer checksum is in `out/migration/SHA256SUMS`.
The machine-readable migration status is `out/migration/test-results.json`.

## Read-only bridge inventory

Configured profile: `bridge`, `user@172.16.10.118:22`; hostname `user-0`,
kernel `7.0.0-31-generic`, x86_64. Commands ran through ssh-mcp. The
read-command allowlist rejected ip/lsusb, so the same read-only inspection
commands were run through run-command.

| Item | Observed state |
|---|---|
| BliKVM UART | `1a86:7523`, `/dev/serial/by-id/usb-1a86_USB_Serial-if00-port0` -> `/dev/ttyUSB0` |
| Host MCU | `3343:803a`, separate `/dev/ttyACM0` |
| UART permission | root:dialout 0660; SSH user is not in dialout |
| USB-PC | `1d6b:0106`, three usbhid interfaces and usb-storage, host port 1-3, 480 Mbit/s |
| Lab NIC | enp1s0, MAC `00:e0:4c:07:f0:0f`, carrier 1, 100/full |
| Lab address | `169.254.221.144/16`; NetworkManager profile `netplan-enp1s0` uses link-local; `192.168.88.1/24` is missing |
| Management | wlo1 `172.16.10.118/24`, default via `172.16.10.1` |
| TFTP | active tftpd-hpa, empty `/srv/tftp`, listening on `:69` (all addresses) |
| Historical TFTP setup | `/var/lib/tftpboot`, old dnsmasq config and service absent |
| HDMI source path | card1-HDMI-A-2 connected, connector ID **287**, previously 283 |
| Moving video source | gst-launch-1.0 absent |

No old checkout, out/runs, Image, manifest.json, or uart.log was found in the
inspected accessible /home, /srv, /opt, and relevant /var/lib locations.
This does not establish the contents of inaccessible directories or other
offline backups. Read-only bridge output is saved under
`out/migration/bridge-readonly.json`.

## Deployment prerequisites and policy blocker

The ssh-mcp service rejected privileged commands, including a privilege
identity probe, with `POLICY_DENIED`: role admin cannot run privileged
commands in inferred host group prod. The profile has no explicit group.
The profile policy must permit the authorized lab operations before changing
the lab address/TFTP binding or accessing the UART with elevation. No bridge
configuration was changed and no target reboot was attempted.

After access is restored, configure isolated `192.168.88.1/24` without a
gateway/DNS, bind TFTP to the lab address, stage VM-built artifacts and the
checked-in labctl on the bridge, and compare hashes before RAM boot. Restore
a bounded moving HDMI source using the currently discovered connector ID.
Archive boot-uvc with retained MMC/Ethernet/USB/UVC checks and download the
run evidence. Only a passing migration boot authorizes proceeding to M5.

### Retry after privileged policy was enabled

The user enabled privileged lab operations. A fresh connection and read-only
identity/network/USB inspection succeeded with the same bridge state. The
privileged `id` probe no longer received POLICY_DENIED, but timed out after
60,000 ms. An explicit `sudo -n id` through ssh-mcp returned
`sudo: interactive authentication is required` (exit 1). The remaining
blocker is usable sudo authentication for the connector, not the earlier
host-group policy. Configure the connector's sudo credential or an appropriate
sudo policy on the bridge before retrying. No passwords were requested in
chat, no bridge configuration changed, and no target reboot was attempted.

### Retry after bridge NOPASSWD sudo was configured

`sudo -n id` now succeeds as root. The bridge NetworkManager profile
`netplan-enp1s0` was changed to manual `192.168.88.1/24`, no gateway or DNS,
never-default, IPv6 disabled. The Wi-Fi management/default route remained
active. The existing tftpd-hpa service now binds only `192.168.88.1:69` and
continues serving `/srv/tftp`; its prior config is saved at
`/etc/default/tftpd-hpa.before-blikvm-migration`.

The VM deployment bundle was transferred to the bridge through a temporary
single-request receiver controlled by ssh-mcp. Its SHA-256 matched
`785e31e590ce9afd82d01afe50cd647b9c9d4dc9fee998b47d8eb4a8c96db25d`.
The bundle is extracted under `/home/user/blikvm-migration`, with the source
checkout at `repo/` and VM-built artifacts at `build-run/`. All five entries
in the build SHA256SUMS passed verification there. No compilation ran on the
bridge. UART opens successfully with sudo.

GStreamer tools/base/bad plugins were installed on the bridge. A ten-second
moving-ball KMS pipeline on connector 287 ran without reporting a sink error
and ended at its timeout (exit 124); no pipeline remains running. This is a
host-side check, not proof that the target captured changing frames.

`boot-uvc` run `20260906T021625Z-8cd48fc-076357` published immutable artifacts
under `/srv/tftp/runs/20260906T021625Z-8cd48fc-076357` and stopped at preflight:
the target is at a vendor Linux authentication prompt and no target password
file was supplied. Last passed stage: deploy. No target reboot, U-Boot
operation, or UVC capture occurred. A bridge-side vendor credential file for
`--target-password-file` or an authenticated UART shell is required next.

The original evidence remains under the bridge checkout's `out/runs/`.
Text evidence was downloaded via SFTP to
`out/migration/bridge-runs/20260906T021625Z-8cd48fc-076357/`; host evidence is
under `out/migration/bridge-restored/`. Connector redactions are retained in
the downloaded text. Binary artifacts remain available on the VM from the
hash-matched build run. An HTTP evidence server was rejected by automatic
approval review and was not started; SFTP provided the safe alternative.

### Authenticated RAM boot and HDMI-path failure isolation

The user supplied the vendor default console credentials documented in the
[BliKVM first-steps guide](https://blikvm.com/docs/getting-started/first-steps/).
The credential is held outside the checkout in a mode-0600 runtime file on
the bridge. It is not included in artifacts or evidence transfers.

Run `20260906T022414Z-8cd48fc-515285` exposed a UART parser problem: the
CH340 flush space appears before `Password:`, but PASSWORD_PROMPT required
the word at the start of the line. The one-line fix permits leading spaces
and tabs while retaining the anchored prompt. Its new regression fixture
also rejects `echo Password:`. All 21 local tests pass. The bridge's labctl
contains this exact uncommitted change; the patch, source hash, and dirty
state are archived under `out/migration/bridge-restored/`.

With this fix, full RAM boot run `20260906T022507Z-8cd48fc-348123` logged in,
rebooted through the existing bootloader, passed the guarded PHY correction,
transferred all three artifacts, and reached the Linux 7.2.3 initramfs shell.
It passed MMC/read-only ext4, Ethernet carrier/address/ping, internal USB1
EHCI/MS2131 identity/topology, UVC binding/node mapping/mode enumeration, and
bounded streaming without persistent USB/UVC errors. It failed specifically
at `uvc_changing_frames`: 60 complete frames, 36,864,000 bytes, zero error
frames, but only two unique hashes and one transition. These are not accepted
as proof of live video.

The bridge now reads EDID monitor name **HDP-V104**, serial text `demoset-1`,
on HDMI-A-2/connector 287. The previous accepted setup identified **HJW HDMI
TO USB**. KMS state confirms an active 1280x720 mode and the videotestsrc
framebuffer. Restarting the source after target boot still failed in run
`20260906T022641Z-8cd48fc-624739`. Initially the bridge drove 12-bit color;
temporarily forcing max bpc to 8 produced confirmed 24-bpp/74.25-MHz output,
but run `20260906T022745Z-8cd48fc-971750` still captured the same frozen
sequence. This leaves HDMI routing/source/signal compatibility unresolved;
it does not establish a kernel regression or prove a specific cable fault.

The user was asked to confirm the physical LattePanda HDMI-output to BliKVM
HDMI-input path and any splitter/adapter. All temporary GStreamer sources
were stopped and connector max bpc restored to 12. The target remains in
the RAM-only UVC initramfs. Its missing host-visible gadget is expected for
this baseline. No M5, Ubuntu-rootfs, PiKVM userspace, or persistent U-Boot/
target-storage changes were made.

The four new runs' text logs and machine-readable results were downloaded
through SFTP into `out/migration/bridge-runs/`. Original bridge logs retain
the raw bytes; local text copies retain connector redactions. The full boot
run's artifacts are the already verified VM baseline. Do not mark migration
passed until a fresh complete boot-uvc run captures changing frames.
