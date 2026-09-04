# Linux 7.2.3 MS2131 UVC/V4L2 bring-up

Status: passed on hardware in two consecutive full RAM-only Linux 7.2.3 boots.
Raw upstream V4L2 capture is proven; USB audio, HID, gadget, target DRM/display,
hardware codecs, uStreamer, kvmd, GPIO/ATX, and the final Ubuntu rootfs remain
disabled or unstarted.

## Minimum kernel and userspace delta

The host-only baseline is commit `b09f56d205924cfc9580fa078468d862f275fbf7`
and annotated tag `linux-7.2.3-usb-host-baseline`. The next config slice adds
only media core, V4L2, videobuf2 VMALLOC support, USB media support, and the
upstream `uvcvideo` driver. Media subdriver autoselection and UVC input-event
support are disabled. Sound, USB audio, DRM, platform media/codecs, MUSB,
gadget/configfs, and gadget functions remain absent.

The initramfs contains one static AArch64 utility, `v4l2-test`, instead of a
large media userspace stack. It enumerates capabilities, formats, discrete
sizes and intervals, inputs, standards, and current state; selects only the
MS2131 capture node; then performs bounded MMAP streaming with per-frame byte,
non-zero-byte, sequence, timestamp, flag, and FNV-1a hash records. One
explicitly flagged short pre-roll buffer may be discarded before the first
valid frame. Repeated pre-roll errors, any error after valid capture starts,
timeouts, empty data, a frozen hash sequence, or a negotiated-mode mismatch
fail the run.

## Binding and device mapping

The device is `345f:2131`, serial `29404080`, sysfs device `1-1`, directly on
`5200000.usb` root port 1 at 480 Mbit/s.

| USB interface | Class/subclass | Upstream driver | Role |
|---|---|---|---|
| `1-1:1.0` / 00 | `0e/01` | `uvcvideo` | UVC video control |
| `1-1:1.1` / 01 | `0e/02` | `uvcvideo` | UVC video streaming |
| `1-1:1.2` / 02 | `01/01` | unbound | USB audio control, deferred |
| `1-1:1.3` / 03 | `01/02` | unbound | USB audio streaming, deferred |
| `1-1:1.4` / 04 | `03/00` | unbound | HID, deferred |

The upstream-only image has no Cedrus or other video nodes, so node numbering
is deterministic in this slice:

| Node | Device capabilities | Function | Sysfs USB parent |
|---|---|---|---|
| `/dev/video0` | `0x04200001` | video capture + streaming | `1-1:1.0` |
| `/dev/video1` | `0x04a00000` | UVC payload-header metadata + streaming | `1-1:1.0` |

Both report bus info `usb-5200000.usb-1` and resolve through
`/sys/devices/platform/soc/5200000.usb/usb1/1-1/1-1:1.0`. The capture node
advertises `MJPG` and `YUYV`; the metadata node advertises `UVCH`.

## Measured capture API

Input 0 is `Camera_1`, current and usable, with no `V4L2_IN_ST_NO_SIGNAL` bit.
Analog standards are not applicable and enumeration returns zero standards.
The device default is MJPEG 1920x1080 at 30 fps.

| Format | Resolution | Advertised frame rates |
|---|---:|---|
| MJPG | 1920x1080 | 50, 30, 25, 20, 10 |
| MJPG | 1600x1200 | 50, 30, 25, 20, 10 |
| MJPG | 1360x768 | 60, 50, 30, 20, 10 |
| MJPG | 1280x1024 | 60, 50, 30, 20, 10 |
| MJPG | 1280x960 | 60, 50, 30, 20, 10 |
| MJPG | 1280x720 | 60, 50, 30, 20, 10 |
| MJPG | 1024x768 | 60, 50, 30, 20, 10 |
| MJPG | 800x600 | 60, 50, 30, 20, 10 |
| MJPG | 720x576 | 60, 50, 30, 20, 10 |
| MJPG | 720x480 | 60, 50, 30, 20, 10 |
| MJPG | 640x480 | 60, 50, 30, 20, 10 |
| YUYV | 1920x1080 | 10, 5 |
| YUYV | 1600x1200 | 10, 5 |
| YUYV | 1360x768 | 15, 8 |
| YUYV | 1280x1024 | 15, 8 |
| YUYV | 1280x960 | 15, 8 |
| YUYV | 1280x720 | 20, 10 |
| YUYV | 1024x768 | 20, 10 |
| YUYV | 800x600 | 30, 20, 10 |
| YUYV | 720x576 | 50, 25, 20, 10 |
| YUYV | 720x480 | 60, 30, 20, 10 |
| YUYV | 640x480 | 60, 30, 20, 10 |

These are descriptor claims. The bounded qualifying mode was deliberately
small and uncompressed: YUYV 640x480 at 30 fps, 60 valid frames per boot.
Higher-resolution and signal-loss qualification remains separate from proving
the raw upstream stack.

## Deterministic HDMI source and failure isolation

The LattePanda HDMI-A-2 output detected the MS2131 EDID as `HJW HDMI TO USB`.
A GStreamer moving-ball source submitted through GDM/Wayland did not appear on
the physical wire even after the CRTC was active; the MS2131 continued to emit
one startup transition followed by a frozen fallback frame. Testing both YUYV
640x480 and MJPEG 1920x1080 produced complete buffers and clean USB logs, which
excluded format, endpoint bandwidth, alt-setting, and transport failures.

For qualification, the host temporarily switched to an unused VT and drove
connector 283 (`HDMI-A-2`) directly with KMS at 1280x720:

```bash
sudo timeout 600s gst-launch-1.0 -q \
  videotestsrc is-live=true pattern=ball animation-mode=frames \
  ! video/x-raw,width=1280,height=720,framerate=30/1 \
  ! videoconvert \
  ! kmssink connector-id=283 force-modesetting=true restore-crtc=true
```

Direct KMS immediately produced a different hash on every captured frame. The
pipeline was stopped after testing, the host returned to GDM VT1, HDMI-A-2 was
left in normal `detect` mode, and the temporary source changes were not made
persistent. This host-side KMS use did not enable target DRM/display support.

## Automated hardware results

Final qualifying runs:

| Run | Result | Valid frames | Bytes | Unique hashes | Transitions | Pre-roll discards | In-stream errors |
|---|---|---:|---:|---:|---:|---:|---:|
| `20260904T062855Z-b09f56d-182887` | pass | 60 | 36,864,000 | 60 | 59 | 0 | 0 |
| `20260904T063907Z-b09f56d-825527` | pass | 60 | 36,864,000 | 60 | 59 | 0 | 0 |

Both runs also passed the command-verified serial shell, MMC0 discovery and
`ro,noload` ext4 read, EMAC1 100/full carrier and 5/5 isolated pings, EHCI1/PHY1
and `usb1-vbus`, direct 480 Mbit/s MS2131 enumeration, interface binding, node
mapping, capability/mode enumeration, and negative dmesg checks. Neither run
contains a persistent UVC probe, reset, URB, bandwidth, timeout, disconnect, or
EHCI failure.

Each run archives `lsusb.log`, `lsusb-tree.log`,
`usb-interface-bindings.log`, `video-node-map.log`,
`v4l2-capabilities.log`, `v4l2-stream.log`, `uvc-dmesg.log`, full UART/dmesg,
artifacts and hashes, metadata, and `test-results.json`.

The final incremental `-j3` build is
`20260904T062819Z-b09f56d-577486`:

| Artifact | Size | SHA-256 |
|---|---:|---|
| `Image` | 6,221,832 | `bba8b2aa83a6b0737b02f208875959f27462e543c57ee150a27d130e85aba015` |
| `sun50i-h616-blikvm-v4.dtb` | 20,552 | `4b94e64517a3eb117e9aa4d9287334a72ba8e82bf448d4d05d08a5ec1ed1f3ef` |
| `initramfs.cpio.gz` | 4,297,497 | `d0f998a9235ceaafeea5b2c053dcf09003254da2724672fc493235a4c6066dd1` |
| `linux.config` | 63,155 | `2231e384676b1567643b5f3cdd76900f6b702b1960c405a7e22e817184b88e39` |

No-change incremental build `20260904T063606Z-b09f56d-718465` reproduced all
four sizes and hashes with `-j3`.

No SD/MMC write, persistent U-Boot environment change, clean build, USB gadget,
USB audio, uStreamer, kvmd/PiKVM, GPIO/ATX, or Ubuntu-rootfs work was performed.
