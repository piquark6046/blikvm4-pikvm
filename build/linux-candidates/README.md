# MS2131 bulk EOF candidate 2

Candidate only, not accepted or added to the normal production patch stack.
M8-F0 remains OPEN, Run 02 remains FAILED, and qualification time is zero.
P1 is gated; M6/ATX is deferred. Diagnostic checkpoint: `f7d1132`.

The kernel and DQBUF evidence in
`research/evidence/m8f0/uvc-diag-02/README.md` demonstrates the same 12-byte
EOF-only suffix already in bulk USB data before uvcvideo decoding/copying.
A transport-aware guard belongs at the bulk decoder: userspace cannot verify
the initial UVC header, negotiated payload size or USB packet boundary.

`ms2131-bulk-eof-reject.patch` adds only an MS2131 device quirk, a bounded
predicate, and explicit per-buffer rejection in the initial bulk-payload path.
It applies to VID:PID 345f:2131, UVC control interface, MJPEG only. The received
transfer must be short, smaller than the negotiated maximum, with a 512-byte
endpoint and the suffix exactly on that packet boundary. Both headers must
have the observed 12-byte format, matching FID/PTS, EOF added only in the suffix,
ERR clear, and valid suffix SCR SOF reserved bits. JPEG EOI must immediately precede
the suffix. No bytes or lengths are trimmed, and no arbitrary header-like data
is removed. All unaffected frames keep their original path.

The whole affected buffer is explicitly requeued at final completion, after
all asynchronous copies finish. The quirk flag is reset on both preparation and
internal requeue. This rejection works with both nodrop settings and preserves
the accepted live `uvcvideo.nodrop=1` value and ordinary error-buffer policy. Losing a malformed frame is intentional,
and the unchanged 27-fps
capacity and continuity gates still apply. This is a narrow containment of the
demonstrated device framing defect, not a repair of device firmware.

The candidate starts from the exact accepted Linux 7.2.3 tree and all accepted
patches. Configuration differs only in LOCALVERSION. No diagnostic ring,
DEBUG_FS enablement or diagnostic uStreamer binary is included. The accepted
M8-E enrolled RAM root (`dadf5f2839f42ae062f793a58a79afb5b2305f01e345a4c2434adbaca29467cb`)
and DTB are reused byte-for-byte. The Image is
`e5022886bc6c839e82f6d967fca1fcdfca8c341c05044f94b59d001e7fe68328`.

Local checks: 123 tests pass, including native compilation of the exact helper
from the patch, negative framing/bounds cases, and UBSan. An additional private
replay reconstructs all 23 faulty bulk payloads from complete completed buffers
plus retained raw headers, verifies their raw boundaries, and recognizes all
23. Correctly separated video and EOF transfers are left alone. The separate
Image builds without warnings; patch application has zero fuzz.

Hardware candidate preflight passed; the remaining M8-E critical gates are
pending. No
24-hour qualification starts until candidate stress has zero malformed escapes
and all required regressions pass. Diagnostic runs never contribute time.

Candidate 1 is permanently failed: the initial implementation assumed nodrop=0,
but the accepted source and live target use nodrop=1. Its preflight was stopped
when that mismatch was verified. The Image, source, patch, boot and partial
preflight remain preserved; `research/evidence/m8f0/ms2131-candidate01/` records
the failure. Candidate 2 changes only the specific quirk rejection path and does
not change the accepted global setting. Native execution of the actual queue
completion/requeue functions verifies all eight nodrop/error/quirk combinations
and successful subsequent reuse of each rejected buffer.

The unchanged uStreamer capture heuristic permits JPEG buffers ending in 00 00
and does not consult V4L2_BUF_FLAG_ERROR. A coalesced EOF header with zero SOF can
therefore escape that heuristic. Merely marking ordinary buffer error is not a
sufficient correction. The new guard covers zero SOF explicitly; the strict
qualification parser is unchanged.

For replay on this build VM, preserve/use the isolated accepted-source snapshot
and apply the candidate patch with `patch --fuzz=0 -p1` into a separate source
copy at `out/m8f0/uvc-candidate-02/source`. The exact build script used is retained
as `build-candidate02-in-container.sh`; it reuses that output's incremental
objects and never cleans the normal kernel tree. Run it in the accepted
`blikvm-linux-builder:bookworm-20260904-uvc-dtschema-2026.6` container with the repo
mounted at `/work` and UID/GID 1000. It pins the build timestamp, user, host and
version. `check-drop.py --source <patched-tree> --output <test-output>` compiles
and executes the actual completion/requeue functions for both nodrop settings.
The public source-delta manifest verifies that only four UVC files differ from
the exact accepted tree.

Candidate 2's fresh preflight passed independent VM replay: 11,163 frames in six
strict-parser sessions, zero malformed payloads observed, both simultaneous
clients above 29.7 fps, 12 HID API runs, 17 storage checks and 54 media transitions.
The real browser and concurrent disk workloads passed. Five full clean boots also passed independent replay, with five distinct boot
IDs and 12 warning/reset-free kernel inventories. Physical USB-PC reconnect
remains pending. All candidate and diagnostic
work still contributes zero qualification time.
