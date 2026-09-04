# HDMI capture path

Status: **raw upstream Linux 7.2.3 UVC/V4L2 capture proven on hardware**.

The connected board contains a MacroSilicon MS2131-family device. The live USB identity is `345f:2131`, manufacturer `MACROSILICON`, product `USB2 Video`, serial `29404080`. It sits directly on H616 USB host 1 (`usb-5200000.usb-1`) at 480 Mbit/s. In the minimal upstream bring-up image it exposes:

- two UVC interfaces bound by `uvcvideo`;
- video capture `/dev/video0` and UVC metadata `/dev/video1`;
- unbound USB audio interfaces; and
- an unbound USB HID control interface.

The vendor OS also enables Cedrus, shifting the vendor capture/metadata nodes to
`/dev/video1` and `/dev/video2`. Node numbers therefore remain unsuitable as a
future persistent identity even though `/dev/video0` is deterministic in this
minimal image.

## Measured modes

The capture node supports MJPEG and YUYV. Relevant examples from the full [raw V4L2 capture](vendor-system/v4l2.txt):

| Format | Resolution | Advertised frame rates |
|---|---:|---|
| MJPEG | 1920x1080, 1600x1200 | 50, 30, 25, 20, 10 fps |
| MJPEG | 1360x768 through 640x480 | up to 60 fps |
| YUYV | 1920x1080, 1600x1200 | 10, 5 fps |
| YUYV | 1280x720, 1024x768 | 20, 10 fps |
| YUYV | 800x600 | 30, 20, 10 fps |
| YUYV | 720x480, 640x480 | up to 60 fps |

The live default is MJPEG 1920x1080 at 30 fps. The complete Linux 7.2.3 mode
matrix and two passing bounded captures are recorded in
[uvc-v4l2-bringup.md](uvc-v4l2-bringup.md). Vendor software searches for the
first `/dev/video*` advertising JPEG and starts uStreamer at 1920x1080/20 fps;
this heuristic is fragile because Cedrus occupies video0 in that OS and
enumeration can change.

## Stable identification

Prefer the standard `/dev/v4l/by-id` link containing serial `29404080`. If a distribution does not create it, install a udev rule matching `SUBSYSTEM=="video4linux"`, USB parent VID/PID `345f:2131`, serial `29404080`, and the capture interface index, producing `/dev/kvmd-video`. A topology-based fallback may match `usb-5200000.usb-1`, but serial is stronger. Also verify `ID_V4L_CAPABILITIES` includes capture so the metadata node is never selected.

## PiKVM test sequence

1. Confirm VID:PID, serial, 480 Mbit/s, and `uvcvideo` binding; keep USB audio deferred.
2. Run `v4l2-compliance` on the stable capture symlink.
3. Capture 300 MJPEG frames at 1920x1080/30 and check decode errors, timestamps, drops, and USB resets.
4. Exercise HDMI signal loss/reacquisition and resolution changes without rebooting.
5. Run upstream uStreamer using MJPEG pass-through; record CPU, memory, latency, and reconnect behavior.
6. Treat audio as optional until video is stable.

The vendor's 4K30 figure describes accepted HDMI input/loop-through, not a verified 4K UVC stream. H.264, where available in vendor releases, is software encoding; it is not advertised by this V4L2 capture device.
