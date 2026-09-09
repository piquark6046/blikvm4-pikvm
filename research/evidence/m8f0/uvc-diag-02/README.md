# M8-F0 kernel diagnostic revision 2

M8-F0 remains OPEN. Run 02 remains permanently FAILED. Qualification duration
is zero; P1 remains gated and M6/ATX remains deferred. No release/baseline tag.

The corrected diagnostic Image booted in RAM in run
`20260909T002127Z-unknown-781413`. Its 300-second preflight passed independent VM
review. All 21 suspicious kernel buffers match complete DQBUF payload hashes,
sequences, exact tails and through-EOI hashes. Metadata/raw counters reconcile;
three nonce flushes are acknowledged; no required ring entries were lost,
suppressed or oversized; no partial output, unexpected reset or kernel warning
was found. Both clients achieved 29.8083 and 29.9417 fps in the two full 120-second
windows. Exact MJPEG 1920x1080 30/1, host HID and read-only MSD regressions passed.
Kernel ring allocation is 37,795,112 bytes. uStreamer used at most 36,798,464 RSS
bytes and 8.8557 percent of one CPU core. Ordinary rolling overwrites are counted
explicitly and are not missing entries required for the captured buffers.

The first subsequent observation (04) failed on an HTTP 502 during kvmd API
startup, with no recurrence. Its immutable wrapper result incorrectly labels
the stop as a bounded deadline; the traceback establishes the startup failure.
The wrapper now waits for the API to answer before starting authenticated clients.
This is a harness startup fix, not an authentication or nginx change.

Observation 05 stopped at a useful recurrence after 5.314 seconds (900-second
maximum). Two kernel events, IDs 22 and 23, match full DQBUF bytes and hashes.
The final flush was created as verified live UID 988/GID 989 and acknowledged
within five seconds. Kernel and userspace counters reconcile with the initial
kernel state; no required evidence is missing. The recurrence occurred during
stream startup, before either HTTP client received frames. This observation
proves cross-layer origin; it supplies no HTTP capacity or downstream escape
claim. The separate completed preflight provides video capacity evidence.

## Classification A: coalesced MS2131 bulk EOF framing

Live descriptors identify bulk IN 0x83, interface 1 alternate 0, 512-byte maximum
packet size. The negotiated maximum UVC payload is 15,360 bytes.

For both new events, the faulty bulk URB contains 10,764 bytes. The decoder
correctly excludes its initial 12-byte UVC header. The JPEG EOI ends at URB offset
10,752 (21 times 512). A further 12 bytes already follow it in the received raw
URB. These bytes equal the selected region, the source immediately before memcpy,
the destination immediately after memcpy, the completed buffer tail, and DQBUF.
There is no asynchronous-copy discrepancy. This establishes A, not a newly
introduced header-selection or memcpy defect in uvcvideo.

The suffix is a 12-byte EOF header with the same FID and PTS as the leading
header, EOF added to bmHeaderInfo, ERR clear, and later SCR. Nearby normal frames
end with a separately received 12-byte EOF-only transfer. The faulty frame has
no separate EOF transfer; the next transfer flips FID and completes it.

The observed mechanism is coalescence of a header-only EOF transfer after a
max-packet-aligned JPEG payload. Missing short/ZLP termination by the device is
the framing explanation consistent with this evidence. We captured completed
bulk URBs, not electrical bus transactions; absence of a wire-level ZLP is an
inference, not a directly measured physical-bus assertion. The byte origin before
uvcvideo decoding and copying is directly demonstrated.

The [USB-IF UVC 1.5 specification set](https://www.usb.org/sites/default/files/USB_Video_Class_1_5.zip)
sections 2.4.3.2, 2.4.3.3 and the Probe/Commit control definition specify header/data
encapsulation, FID/EOF/PTS/SCR and maximum payload size. Bulk short-packet termination
is also described in [Microsoft's USB transfer documentation](https://learn.microsoft.com/en-us/windows-hardware/drivers/usbcon/usb-bandwidth-allocation).

## Smallest candidate to evaluate

A narrow MS2131 bulk-MJPEG guard can mark the entire buffer corrupted when the
observed framing signature is present: exact device, leading 12-byte header,
512-byte-aligned suffix position, short final transfer below negotiated maximum,
JPEG EOI immediately before the exact 12-byte EOF-only suffix, matching FID/PTS
and expected flags. Existing corrupted-buffer handling then rejects the frame.
It must not trim a suffix or reinterpret arbitrary header-like bytes. No
production correction is accepted by this diagnostic result. A non-diagnostic
candidate still needs bounded video/HID/MSD stress, zero malformed escapes and
all M8-E critical regressions before a new continuous 24-hour qualification.

Private raw archives remain outside Git. The preflight archive has SHA-256
`0fb999946b15483752bbc0f6bd86e0fbabed38cfa6a02e153f4879375505b906`
(9,581,750 bytes, 352 files). Observations 04/05 archive SHA-256 is
`dac5c738c23c84daf2479adae5d69505779a0ada11a5a301d7331079ebc3d3fb`
(594,825 bytes, 65 files). Both were independently hash-verified after download.
The original failed diagnostic boot remains under `../uvc-diag-01-failed/`.
