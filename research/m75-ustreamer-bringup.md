# M7.5 pinned uStreamer service qualification

Status: **PASSED** on two clean RAM-only boots of the corrected package. M7 is frozen at
`ubuntu-26.04.1-rootfs-baseline` (`222f61f`); M6 GPIO/ATX remains **DEFERRED**.
No kvmd or other PiKVM service is installed by this slice.

## Source and packaging

Rechecked upstream on 2026-09-06 before implementation. The current
[PiKVM PKGBUILD](https://github.com/pikvm/kvmd/blob/master/PKGBUILD) requires
`ustreamer>=6.47`. Upstream uStreamer packaging names release 6.65. The live Git
ref query resolves `v6.65` to `db87e03ce769d06ba62314ca7537e1cb3369b4de`.
The dependency declarations and ref query are retained in
[evidence/m75-ustreamer](evidence/m75-ustreamer/).

Pinned source URL:
`https://codeload.github.com/pikvm/ustreamer/tar.gz/db87e03ce769d06ba62314ca7537e1cb3369b4de`.
Archive SHA-256: `af99973b821b1e06ad9dbebc063ceb8ca868e06af7a6ccd90e67dc1d0a7fafea`.
The builder checks this before extraction, with no moving branch input.

`build/ustreamer/` extends the M7 workflow by extracting its exact frozen tarball
into independent package-build and runtime trees. The AMD64 VM performs ARM64
GCC compilation under the existing isolated QEMU namespace, using the frozen
Ubuntu package snapshot. Native AMD64 dpkg-deb assembles the resulting ARM64
payload. Neither bridge nor target compiles anything. The runtime image has no
compiler/build dependencies. Original M7/M5 artifacts and kernel object trees
remain unchanged. All deployment is RAM-only through the accepted U-Boot/TFTP
transport; no recovery-SD or persistent U-Boot environment writes occur.

The final package is `ustreamer_6.65-1blikvm2_arm64.deb`, built from the exact
upstream archive plus the separately hashed capture-controls patch described
below. Two complete fresh package builds and two fresh runtime builds reproduce
the corrected artifact hashes. Earlier `6.65-1blikvm1` results are rejected for
selecting the wrong camera frame rate; their original evidence is retained.

## Stable identity and service

The live device reports vendor/product `345f:2131`, serial `29404080`, USB
480 Mbit/s and `ID_V4L_CAPABILITIES=:capture:`. The udev rule matches all four
properties, excluding the metadata node without depending on video numbering.
It creates `/dev/kvmd-video`, grants its dedicated `ustreamer` group mode 0660,
and supplies a systemd device alias and activation request.

The unprivileged service binds to and starts after that device unit. The corrected service requests
1920x1080, 30 device fps, MJPEG and the HW encoder (upstream's JPEG copy/pass-through
path), with no H.264 option. Its private Unix HTTP endpoint is
`/run/kvmd/ustreamer/ustreamer.sock`. systemd removes the runtime directory on
stop and kills the complete process group. The dedicated account's device access is enforced by udev ownership/mode.
DevicePolicy/DeviceAllow also express the intended future cgroup filter, but
the frozen M7 kernel lacks BPF_SYSCALL, so no BPF device-filter enforcement is
claimed on this kernel. The account is not a member of the general video group.

## Qualification method

Archive full V4L2 formats before streaming. The live device advertises MJPEG
1920x1080 at 30 fps, so that is the primary mode. Discover the bridge's HDMI-A-2
connector ID at runtime (currently 287, different from older evidence). A
GStreamer moving ball directly drives KMS at 1920x1080/30.

The bridge client parses HTTP multipart frames carried over authenticated SSH
from target curl accessing the Unix socket. It records every frame's byte count,
SHA-256 and arrival time; requires nonempty JPEG markers, at least five frames
per second overall, no gap beyond three seconds, and changing hashes in every
complete five-second window. This proves bounded continuous moving video,
without claiming an exact 30 delivered fps threshold.

Three stop/start/restart iterations check process and socket cleanup. Three
signal-loss cycles stop the source and set connector DPMS Off, archive the Off
property and no-signal stream behavior, restore source motion, and require the
same uStreamer PID with moving frames again. Intentional no-signal client
failures are archived separately from recovery results. Frozen M5 descriptor,
keyboard, absolute/relative mouse and RO storage tests execute with streaming;
whole-image storage reads and HID reports also overlap a client stream.

## Negative and provisional results

* First builder invocation used a different registration pathname from the
  existing binfmt helper; the lookup failed before root extraction. The
  container-private namespace was discarded. Use the helper's exact registered
  name. Log: `out/ustreamer/package-build-registration-failed.log`.
* Initial ARM64 compilation succeeded, but dpkg-deb's ARM64 tar subprocess
  returned `Function not implemented` for file metadata calls under QEMU.
  Native builder dpkg-deb assembles the ARM64 files successfully. Log:
  `out/ustreamer/package-build-tar-failed.log`.
* Provisional boot `20260906T095805Z-unknown-188136` passed the existing Ubuntu
  settled-systemd/Ethernet/SSH gates with automatic uStreamer startup.
* HIL `20260906T095929Z-unknown-508516` failed in the client before counting
  frames: the client incorrectly required HTTP/1.1, while upstream returned a
  valid HTTP/1.0 200 response. Both protocol versions are now accepted; a local
  regression test covers the actual response. The failed run remains intact.

The acceptance gate required final-package reproducibility, complete HIL on
multiple clean boots, and review of full journals and USB logs; the final
results appear below.

* Provisional HIL `20260906T100004Z-unknown-167969` passed its 60-second stream
  (1,486 distinct frames, 61,642,538 bytes) and all six start/restart streams,
  but **failed** the HDMI-loss gate. Closing modetest restored fbcon and DPMS
  returned to On. No no-signal qualification is claimed for that attempt. The
  bounded `hdmi-off.py` helper now holds DRM master open; a live readback verified
  DPMS Off while it held the descriptor.

The upstream JPEG capture setup probes optional `VIDIOC_G_JPEGCOMP` on every
open. MS2131 does not implement this control; upstream emits one ERROR-level
`Device doesn't support setting of HW encoding quality parameters` message,
then uses the camera's native JPEG quality and streams successfully. This is
an unsupported optional capability probe, not a buffer/USB streaming failure.
It is retained verbatim, not suppressed or relabeled in raw evidence. These messages belong to the rejected unpatched payload. The corrected
package skips the unsupported operation explicitly and its audit rejects every
uStreamer ERROR-level message.

Final-payload boot `20260906T100555Z-unknown-650516` passed Ubuntu readiness.
Its HIL `20260906T100704Z-unknown-669951` passed a 120-second stream (2,981
unique frames, 123,659,077 bytes), all six start/restart streams, three
DPMS-Off/restoration cycles with unchanged uStreamer PID, and keyboard/both
mice/read-only storage during streaming. **The run remains FAILED:** its final
process-count audit used `pgrep -x ustreamer`, but upstream renames the main
thread to `main`. That also left the `ps -C ustreamer` RSS sample empty (cgroup
CPU samples were present). The corrected runner identifies the executable via
`/proc/PID/exe`, requires the systemd MainPID to be the only process in its
cgroup, scans for escaped copies of that executable, and samples RSS by MainPID.
A complete fresh run is required; the old partial checks do not accept the slice.

## Rejected 50-fps device mode and explicit capture controls

The independent mode audit rejected HIL `20260906T101436Z-unknown-860501`
despite its runner-level pass. **That pass flag is not acceptance.** Its V4L2
readback was MJPEG 1920x1080 at **50 fps**, while `/state` reported desired 30,
captured 50 and queued 25. Upstream `_capture_open_hw_fps()` always requests the
camera maximum; `--desired-fps` controls frame thinning rather than the device
interval. All earlier 24.8-fps results therefore qualify neither the requested
30-fps camera interval nor this milestone. The additional clean boot
`final-boot3.json` used the same rejected payload and is not an acceptance boot.

The pinned upstream commit remains unchanged. Package `6.65-1blikvm2` applies
one separately hashed downstream patch, `build/ustreamer/capture-controls.patch`:

* `--device-fps=N` explicitly requests that V4L2 frame interval. Its default 0
  retains upstream's maximum-rate behavior; this service requests 30.
* `--quality=0` leaves native MJPEG quality untouched and skips the optional
  JPEG-quality ioctl. The default remains 80 for existing upstream behavior;
  this service explicitly selects 0 because MS2131 has no such control.

The patch does not change the USB/UVC kernel, frame contents, HID descriptors,
storage semantics or codec selection. Both the runner and independent auditor
now require the exact device-mode readback; the auditor rejects every uStreamer
ERROR-level message on the corrected payload, without a quality-probe exception.
The builder checks the patch SHA-256, compiles it into a versioned package and
checks valid/invalid CLI arguments. Reproducibility and full two-boot HIL gates
must be repeated on this corrected package before acceptance.

A repeated patched package build generated matching package bytes but its
wrapper failed while reading a script edited during execution (unexpected EOF
in the final summary commands). It is retained as
`out/ustreamer/package-blikvm2-build2.log`, not counted as a successful complete
build. The wrapper now copies its script to a private container path before
execution. Stable-script builds 1 and 3 both completed, and their package/binary
hashes match. Both fresh corrected rootfs builds also completed with identical
bytes. The successful logs are enumerated in the reproducibility record.

Corrected source patch SHA-256:
`7b425f0954c25e35176f59aca157cfe2148b710c9ba40b119438d9a220e8cf4e`.

| Corrected artifact | SHA-256 |
| --- | --- |
| ARM64 binary | `e5a489c828299bc28de71789414312510198c6d7da63b2b18c300bef6313e71b` |
| Debian package 6.65-1blikvm2 | `bc8f5358a955d65fe30641a9a4012e2044c4765086093dccd509e7575038b0a1` |
| rootfs tar/gzip | `9cd7f5bfdd683febd2b6a1fc1d91801e03953e19beee166fd0855b2a24c3f87c` |
| RAM cpio/gzip | `70a81764b2b3f46f9e46f2ff520a4ab70ca5f846b4cd946cfc664bef11dbb21c` |
| runtime package inventory | `82c79bcf2a5f17e2f82d7c1a2ae8d04d0024ea3ec37460a14b9bb380839c9513` |

The corrected RAM image is 61,987,947 bytes and retains M7's exact Image/DTB.
The runtime builder verifies the pinned Debian package digest before install.
The corrected sustained test requires at least 27 delivered fps (90% of the
requested 30) in addition to exact 30-fps V4L2 readback and changing frames.

## Acceptance

The corrected package passed complete HIL and the independent video/reboot
auditors on two distinct, consecutive clean RAM-only boots:

| HIL run | Boot run | 120-second frames | Bytes | Unique hashes | Delivered fps |
| --- | --- | ---: | ---: | ---: | ---: |
| `20260906T103530Z-unknown-473926` | `20260906T103359Z-unknown-021196` | 3,563 | 147,801,730 | 3,563 | 29.69 |
| `20260906T104315Z-unknown-542887` | `20260906T104141Z-unknown-151173` | 3,579 | 148,465,402 | 3,578 | 29.82 |

Both boots selected the same serial/capture identity through `/dev/kvmd-video`,
automatically started the unprivileged service, and negotiated native MJPEG
1920x1080 at **30.000 (30/1)**. Each run passed three explicit stop/start/restart
iterations, with no remaining executable process or stale socket after stops
and exactly the expected systemd MainPID/cgroup after restarts.

All six HDMI-loss cycles held DPMS Off for the bounded no-signal check and
returned to changing video automatically. uStreamer retained PID 1907 throughout
all three cycles on the first boot and PID 1927 on the second. The MS2131 keeps
its USB video stream online while HDMI is off, emitting static frames: the
no-signal clients correctly failed their motion check. Thus `/state`'s `online`
flag describes capture availability, **not HDMI signal presence**. Recovery
clients received 436-437 frames in each 15-second window without a service
restart. The source/DPMS processes were stopped and the bridge returned to VT1.

Both runs passed the frozen keyboard, absolute mouse, relative mouse and
read-only MSD checks, including exact descriptors, input events, file contents,
and rejected filesystem/SCSI writes. Each also completed 22 verified whole-image
storage reads while HID reports and MJPEG streaming overlapped (431 and 434
client frames in the respective 15-second concurrent windows). Ethernet/SSH,
MS2131 identity/high-speed USB, and USB0 composite enumeration remained intact.

RSS was 30,780 KiB on the first sustained run and 30,036-30,236 KiB on the second.
CPU cgroup-counter deltas over the resource sampling windows averaged 2.86% and
2.85% of one core. Raw process/cgroup samples are archived; this is bounded
qualification, not a claim about a 24-hour soak or long-term memory behavior.

The accepted uStreamer journals contain **no ERROR-level messages**, and the
USB/UVC checks found no unexpected errors or USB resets. INFO-level EOF/broken
pipe messages are normal consequences of intentionally disconnecting bounded
HTTP clients. SCSI's initial power-on unit attention is not a USB bus reset.
The frozen M7 masked/generated-unit preset diagnostics are unchanged (verified
against M7's accepted dmesg); both new boots have zero failed systemd units.
No BPF device-filter enforcement is claimed on the unchanged M7 kernel; the
service's dedicated account/device mode is verified, including denial of access
to the metadata node.

The [machine-readable acceptance record](evidence/m75-ustreamer.json) links the
independent gates, reproducibility checks, resource statistics, all accepted
runs, and the explicit rejection of earlier unpatched pass flags. Selected
formats, identities, permissions, service state and full uStreamer journals are
in [the evidence directory](evidence/m75-ustreamer/). The complete archive is
`out/ustreamer/m75-evidence.tar.gz`, 2,873,866 bytes, SHA-256
`7cbf878e5cac59435794afa479bd373d19525f77c9ae44ef0ae3a3dff44f8088`.
It contains UART/U-Boot and target/host logs, per-frame hashes, all negative and
provisional runs, exact artifact/source manifests, upstream source, build logs,
and verifier sources. The original payload manifest says `not_qualified` because
it was generated before HIL; the independent acceptance record is authoritative.
The reviewed source manifest records final source-file hashes separately.

65 local tests pass, including rejection of the earlier 50-fps mode mismatch.
The annotated tag is `ubuntu-26.04.1-ustreamer-baseline`. M7 and M5 remain frozen;
M6 remains deferred. No kvmd, nginx/web UI, authentication integration, GPIO/ATX,
Janus, H.264, VNC, IPMI or final read-only-root work was started.

## Proposed next slice: video-only kvmd

1. Recheck and pin kvmd plus the required Ubuntu Python dependencies; build a
   versioned Debian package on the VM. Define a BliKVM video-only profile with
   the qualified capture identity and native-MJPEG arguments.
2. Resolve streamer ownership before enabling kvmd: use one process owner and
   preserve the qualified device rate, native quality and Unix-socket contract.
   Verify kvmd's external-streamer support; if it must own the process, qualify
   that service handoff explicitly.
3. Expose only a loopback API reached over the existing SSH path. Test state,
   snapshots/streaming, HDMI-loss recovery and clean reboot. Keep this next
   proposal limited to video, with the other integrations deferred.
