# M8-D D0 — HID ownership decision

Status: implementation decision, not hardware acceptance. Parent is frozen
`ubuntu-26.04.1-kvmd-lan-baseline` (`67c9d34`). M6 remains deferred.

## One owner per layer

Keep `initramfs/gadget-storage`, `hid-relative-mouse`, `hid-absolute-mouse`
and `hid-keyboard` as the sole configfs lifecycle implementation. A root
oneshot service will invoke these unchanged helpers once per RAM boot, then
resolve permissions and names before kvmd starts. Only this lifecycle service
may create or bind `blikvm_m5`. Software rebind testing must stop kvmd first,
then use the same owner. Physical reconnect does not recreate configfs.

kvmd runs as its existing unprivileged account. Its pinned OTG backend owns
the three open HID character devices and report queues. The lab harness must
not write reports directly while kvmd owns those devices. Kernel f_hid owns
character-device allocation; names are resolved from each function's `dev`
attribute, `/sys/dev/char/<major>:<minor>`, and the node's actual `st_rdev`.
Only the accepted three nodes receive kvmd access. A root-owned mapping
record will retain function, descriptor hash, sysfs path, device number and
stable link. No wildcard device permission or writable configfs is granted.

Do not install or start `kvmd-otg`, `kvmd-otgconf`, or a second gadget service.
In pinned kvmd 4.213 (`387846d22fa807f97de09750c32c1c9b26d36c1c`),
`kvmd/apps/otg/__init__.py` creates functions, writes descriptors, binds UDC,
and delegates writable configfs attributes to runtime accounts. That would
replace the accepted lifecycle and layout. Conversely,
`kvmd/plugins/hid/otg/__init__.py` accepts keyboard/mouse/mouse_alt device
paths, starts report workers, and switches `usb`/`usb_rel` by choosing a worker
and clearing the previous worker. It does not require the otg helper to run.

## Required narrow port changes

The pinned `kvmd/usb.py:is_udc_configured` hardcodes gadget name `kvmd`.
Point its read-only status lookup at `blikvm_m5`; do not rename the gadget.

The pinned `otg/events.py:make_mouse_report` emits 6/7 absolute or 4/5 relative
bytes including wheels. Frozen M5 expects exactly 5 absolute or 3 relative
bytes, three buttons, no wheels. Adapt this package's serializer to that
layout and ignore unsupported wheel/back/forward inputs. Preserve upstream
signed API coordinates and `MouseMoveEvent` conversion to 0..32767. Neither
report descriptors nor configfs report lengths may change.

Restore upstream HID construction, `HidApi`, subsystem lifecycle and HID state
broadcasts into the M8-C package. Restore only Web UI HID socket transport;
leave recorder transport disconnected. No MSD/ATX/GPIO subsystem or API is
registered. Jiggler stays disabled. Inventory any newly imported dependencies
against the existing package lock before adding packages.

Upstream `htserver.py:_ws_loop` authenticates only the handshake. Upstream
`AuthManager.logout` invalidates all the user's sessions, but does not close
their existing sockets. M8-D must reject revoked sessions before dispatching
each WebSocket message, close invalidated sockets, and clear HID state on
disconnect/logout. Retain the upstream HTTP authentication and wire formats.
Restore upstream HID cleanup during service shutdown; qualify held-key/button
restart and cancellation behavior against grabbed host evdev devices.

## Acceptance gate established before implementation

At decision time, D1–D12 were unqualified. Local tests, live mapping, permissions, exact host
events, browser transport, revocation/cleanup, physical reconnect, concurrent
120-second video and two-client regression, and five clean boots are required
before the final bring-up report, commit, tag or push.

## Initial implementation and USB blocker — 2026-09-07

Candidate package `kvmd-web 4.213-1blikvm3` builds against the frozen snapshot.
82 local tests pass; candidate checks retain 338 runtime files plus all M5
helpers, descriptors and storage bytes. The first RAM boot
`20260907T012155Z-unknown-623279` passes userspace startup, deterministic live
mapping, narrow permissions and the inherited M8-C inventory. The live HTTP
preflight rejects unauthenticated input and invalid credentials, permits
authenticated HID state, invalidates logout, and retains absent MSD/ATX/GPIO
and switch routes. These are scoped checks, not HID functional acceptance.

USB-PC was already absent from the bridge inventory before implementation.
The prompted physical reconnect produced host descriptor-read/setup-address
errors `-71` (EPROTO), with target UDC state `default` and MUSB endpoint-zero
`SetupEnd came in a wrong ep0stage` messages. Stopping kvmd and using the
unchanged helpers to unbind/rebind did not recover enumeration.

Isolation boot `20260907T012746Z-unknown-326164` loads the exact frozen M8-C
private image and then invokes its unchanged M5 gadget helpers. It reproduces
the same enumeration failure without the M8-D package. This rules out an
M8-D-specific package regression as the sole cause; it does not yet establish
whether cable, host port, or controller state is responsible. The target is
left on this frozen M8-C isolation image. A monitored known-good USB-PC data
cable/different LattePanda port check is requested. Other cables stay attached.

First-startup evidence: `out/kvmd-hid/first-startup-evidence.tar.gz`, SHA-256
`d24726a87a21a03df7f442ab0b57d141d49e365428abb5ddc845d333412857d9`.
Failed physical/software/frozen-baseline isolation evidence, including both
boot runs: `out/kvmd-hid/usb-enumeration-negative.tar.gz`, SHA-256
`b95fd5fca71c4334daa9ca03a8fb158ae9522dd47de46d31f3ecd29c16276497`.
Both archives were downloaded using authenticated SFTP and hashes matched.
The failure remains failed. No host input, browser HID, D9 or five-boot gate
has passed; no release commit/tag/push has been made.

### Subsequent recovery and functional work

The next user-confirmed physical intervention restored all four interfaces
at bridge USB path `1-3`. Candidate boot
`20260907T013300Z-unknown-717790` then enumerated successfully and the grabbed
host API sequences passed for keyboard, absolute and relative mice. The earlier
isolation-image statement describes the state at that failed run, not the
current target. Initial recovery does not count as the fresh D9 reconnect gate.

Browser harness development retained negative runs for incorrect CSS geometry,
headless pointer-lock recenter cancellation, unchanged absolute coordinates
(which correctly produce no new evdev event), host autorepeat, and submitting
login before kvmd HTTP readiness after restart. The headed browser uses native
X11 relative input and Escape, normal Web UI mode selection, and the original
kvmd WebSocket transport. It checks browser-observed movement, outgoing packet
bytes and exact host events independently. Only the grabbed keyboard's host
repeat settings are temporarily disabled and restored on exit. Report descriptors
and browser coordinate range remain unchanged; absolute tolerance is one unit.
These harness corrections do not convert any earlier failed run into a pass.

### Direct input scope correction

Review also found that upstream `/hid/print` and
`/hid/events/send_shortcut` schedule delayed events across await points. They
are optional to the required direct keyboard/mouse path and could outlive
logout cleanup. The revised candidate does not register those HTTP routes,
keeps paste UI disabled, and leaves the macro recorder disconnected. The
upstream direct event endpoints and JSON/binary WebSocket formats are unchanged.
No replacement API is introduced. The acceptance boot sequence must restart
on this revised candidate; earlier candidate passes remain developmental.

A developmental 120-second browser workload with a second measured video
client passed at 29.78 fps while repeatedly exercising normal keyboard,
absolute/relative modes and host evdev verification. Earlier workload failures
include a partial JSON handoff (now atomic), one malformed JPEG, and a video
helper's global-user logout invalidating ongoing HID tests. The malformed frame
run remains failed; subsequent instrumentation retains malformed bytes if it
recurs. Shared-session helpers now leave logout to the combined runner.
The unchanged JPEG validation, 120-second duration and 27-fps thresholds remain.
The first candidate package, public rootfs tar and initramfs were independently
rebuilt byte-for-byte; the revised candidate still needs its own final hashes.

## Final disposition

All gates passed on the revised direct-input candidate. See the
[final M8-D report](m8d-kvmd-hid-bringup.md) for the accepted image, five boots,
raw-event replay and archive. The developmental outcomes above retain their
original status. M6 remains deferred and kvmd MSD control remains disabled.
