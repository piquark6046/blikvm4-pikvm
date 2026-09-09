# M8-F0 uvcvideo diagnostic candidate

Diagnostic only. The normal kernel patch stack and accepted M8-E artifacts
are unchanged. M8-F0 remains OPEN; Run 02 remains FAILED; qualification duration
is zero; P1 is gated and M6/ATX is deferred.

The hardened userspace preflight passed independent VM review: 21/21 DQBUF
anomalies retained without suppression, 21 complete payloads, three nonce
acknowledgements, exact 30/1, two-client capacity, HID/MSD and resource gates.
Live MS2131 serial 29404080 uses bulk IN endpoint 0x83, interface 1, alternate 0,
wMaxPacketSize 512. See `research/evidence/m8f0/harness-02/`.

`uvc-taildiag.patch` applies separately to the exact accepted Linux 7.2.3 source.
The source archive pin and all accepted board/EMAC/MUSB patches remain in force.
No diagnostic patch is added to the ordinary builders. Build with the accepted
M8-E kernel configuration, DEBUG_FS enabled and a distinct diagnostic local
version. DEBUG_FS also selects BLK_DEBUG_FS and its access-policy defaults;
no media, USB, gadget, networking or authentication policy is changed.

Both bulk and isochronous decode paths record bounded raw first/last bytes,
header flags and PTS/SCR fields, returned header length, a 64-byte window around
the decoded header boundary, destination V4L2 identity/bytesused and selected
copy offsets/lengths/edges. Each async operation carries its packet ID and
records source edges before memcpy and destination edges immediately afterward.
The completion hook runs on the final buffer kref release, before delivery or
error requeue. It scans markers only; it never changes bytesused or bytes.

A per-stream ring retains 512 packet and 512 copy records. Eight preallocated
snapshot slots each retain those rings and up to 4 MiB of completed payload,
including the exact complete tail. Memory is reported by `taildiag-state` and
bounded below 48 MiB. Only matching MS2131 capture streams allocate it. No
high-volume printk or USB-packet hashing is added.

Debugfs `usb/uvcvideo/*/taildiag-state` reports packet/copy/frame totals,
suspicious/admitted/acknowledged/suppressed events, oversized buffers, required
ring loss, and ordinary rolling packet/copy evictions. Rolling history is not
proof of clean older data. Any overwritten record needed to reconstruct a
completed buffer is an evidence gap; the offline reader independently requires
contiguous full-buffer copy coverage and matching packet IDs. Preflight must
have zero required-evidence loss, suppression or oversized events.

Root-only `taildiag-event0` through `taildiag-event7` expose an explicitly
versioned little-endian binary snapshot. Scalar fields are signed 64-bit;
array and ring sizes are in `uvc-taildiag-schema.json`. Each open gets a stable
copy. The collector saves raw snapshot, completed bytes and decoded records
before acknowledging that exact event ID to release its slot. Missing/partial
records and changed source/destination boundary bytes remain visible. The
collector has a separate 64 MiB raw-input limit and bounded deadline.

`lab/uvc-taildiag-preflight.py` combines this collector with the hardened
userspace preflight. `lab/uvc-diag-boot.py` retains the accepted RAM boot engine,
with publication names containing both Image and initramfs hashes so an unchanged
RAM root cannot select an older kernel's publication. DTB and the hardened RAM
root are byte-identical to harness revision 2.

Native tests: 117 tests pass, including cross-boundary parser, missing-ring,
async disagreement and partial-output fixtures. Separate diagnostic Image builds
without warnings; kernel HIL preflight passed independent VM review. No production correction is
proposed from these implementation or build results.

## Failed boot and corrected candidate

The first diagnostic Image `41bd1422ba462fc63ad2ca3652172dfb1868d7608923c541a1aeff603b6f29a3`
failed boot with an Oops in `__fget_light+0x38` and a recursive fault in
`filp_flush+0x18`. It is permanently failed diagnostic evidence. Its patch
incorrectly inserted a field before the required offset-zero `vb2_v4l2_buffer`
member. This violates the explicit `buf_struct_size` contract documented in
`include/media/videobuf2-core.h`; it is an instrumentation defect, not evidence
of the original JPEG-tail mechanism. The complete failed Image, patch, vmlinux,
System.map and boot trace are retained under `out/m8f0/uvc-diag-01/failed-build-01`
and the immutable artifact directory. Selected failure metadata is in
`research/evidence/m8f0/uvc-diag-01-failed/`.

The corrected candidate keeps the vb2 member first and adds a compile-time
layout assertion. It also accounts for asynchronous copies completing out of
packet order when checking retained history. It builds without warnings as
`7.2.3-blikvm-v4-m8f0-uvcdiag2`; Image SHA-256 is
`4aefd2b4f02405ff4b450bd899d2ce04dce631c7dd70c45b772df6f584e38fd6`.
The patch applies with zero fuzz to the accepted source. All 117 local tests
pass. The corrected kernel booted through the RAM/TFTP path after physical
power recovery, run `20260909T002127Z-unknown-781413`, and passed the normal
network/SSH boot gate. The earlier reboot-acquisition failure remains failed;
it never loaded the corrected Image. Kernel HIL preflight passed independent VM review.
The corrected image is staged at bridge `m8f0-uvcdiag-02/artifacts` and TFTP
`m7/617455ba722e-4aefd2b4f024`. Observation 04 failed at API startup; observation 05 captured a useful A recurrence.
See `research/evidence/m8f0/uvc-diag-02/README.md` for evidence and limits.
