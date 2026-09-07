# M8-D — authenticated kvmd keyboard and mouse control

**PASSED — 2026-09-07.** The authenticated browser → HTTPS/nginx → pinned
kvmd API/WebSocket → HID backend → frozen configfs functions → USB-PC →
LattePanda evdev path is qualified. Five consecutive complete RAM boots,
fresh physical reconnect, service lifecycle, and simultaneous 1080p30 video
passed. Release tag: `ubuntu-26.04.1-kvmd-hid-baseline`.

Parent: `ubuntu-26.04.1-kvmd-lan-baseline` (`67c9d34`). M6 GPIO/ATX remains
explicitly **DEFERRED**. kvmd MSD control, optional integrations, and the final
read-only-root layout are outside this release.

## D0 — one owner at each layer

The [ownership decision](m8d-hid-ownership.md) was established before
implementation against upstream kvmd 4.213, commit
`387846d22fa807f97de09750c32c1c9b26d36c1c`.

| Layer | Owner and responsibility |
| --- | --- |
| USB0/configfs lifecycle | Root `blikvm-gadget.service` invokes the unchanged M5 `gadget-storage setup` and `hid-keyboard bind` helpers. This is the sole gadget owner. |
| HID character devices | Kernel `f_hid` allocates nodes; a root resolver validates identity and grants access only to the accepted three nodes. |
| Reports and open HID descriptors | Unprivileged kvmd OTG backend owns its keyboard and two mouse workers. HIL never writes HID reports directly alongside kvmd. |
| Video | The unchanged kvmd streamer subsystem owns exactly one uStreamer child. |

Upstream `kvmd-otg` creates functions, writes descriptors, binds the UDC and
delegates configfs access. It is not installed or started here. The upstream
HID backend independently accepts device paths and can consume the existing
character devices. A production lifecycle migration is unnecessary for this
slice and remains separate. Only `blikvm_m5` exists in configfs.

## D1–D3 — stable identity, narrow restoration and permissions

The resolver validates the bound controller's sysfs parent `5100000.usb`, the
exact four-function layout, descriptor bytes, report lengths, protocol/subclass,
`no_out_endpoint`, and configuration links. It resolves each function's `dev`
attribute through `/sys/dev/char/<major>:<minor>`, confirms the sysfs device
number, and checks the character node's actual `st_rdev`. It validates all
three functions before changing permissions. Numbering is never inferred.

Observed mappings were identical through software rebind, physical reconnect,
kvmd restart and all five boots:

| Function | Observed major:minor / node | Stable kvmd path |
| --- | --- | --- |
| `hid.keyboard` | `251:0` / `/dev/hidg0` | `/dev/kvmd-hid-keyboard` |
| `hid.absolute` | `251:1` / `/dev/hidg1` | `/dev/kvmd-hid-absolute` |
| `hid.relative` | `251:2` / `/dev/hidg2` | `/dev/kvmd-hid-relative` |

These are observations, not configuration assumptions. An independent fixture
reorders the accepted nodes to 9, 2 and 6 alongside unrelated node 0; resolution
still follows function identity. Mismatched device numbers, descriptors and
extra functions fail closed. Live mappings are archived in
`/run/kvmd-hid/mapping.json` and the per-phase inventories.

The package restores upstream HID construction/lifecycle, `HidApi`, state
broadcasts, and the Web UI HID socket. The only descriptor-compatibility changes
are a read-only gadget-name lookup and report serialization: frozen absolute
reports are five bytes (`<BHH`), relative reports three bytes (`<Bbb`), and
only three buttons exist. Unsupported wheel fields are omitted. Keyboard
reports and every frozen descriptor remain unchanged.

`kvmd-web 4.213-1blikvm3` adds exactly these runtime dependencies from the
inherited immutable Ubuntu snapshot `20260906T000000Z`:

| Package | Pinned version | Required import |
| --- | --- | --- |
| python3-xlib | 0.33-5 | Upstream HID/keymap module |
| libxkbcommon0 | 1.13.1-1 | Upstream keyboard conversion module |
| xkb-data | 2.46-2 | libxkbcommon data dependency |

The complete package lock is checked during construction. The package, public
rootfs tar and initramfs each reproduced byte-for-byte in independent builds.
The existing upstream module imports are retained even though optional delayed
text generation is excluded.

Each accepted node is owned by kvmd, mode 0600. The existing unprivileged
service receives explicit device allowances: keyboard read/write, each mouse
write. It receives no writable configfs, storage attribute, GPIO or sudo access.
Live account checks deny MMC partitions/device, UART and the unrelated video
node; no unrelated HID/GPIO nodes are present. Unit policy has no HID wildcard.

Macro recording/playback and paste remain disabled in the actual UI. The
optional delayed `/hid/print` and `/hid/events/send_shortcut` handlers are not
registered, avoiding input generation that could outlive logout cleanup.
Jiggler remains disabled. MSD/ATX/GPIO APIs remain absent. No replacement HID
API is introduced.

## D4–D8 — host events, browser mapping, modes and authorization

The bridge identifies each evdev device by the frozen composite USB identity
and interface topology, then EVIOCGRABs all three devices. Browser tests
save and temporarily disable repeat on that keyboard only, restoring it before
releasing the grab. Every test cleans up while the devices remain grabbed.
Raw timestamped EV_KEY/EV_ABS/EV_REL and EV_SYN records are retained.

Authenticated API keyboard tests verify ordered Shift press/release, A
press/release, Shift+A, repeated A, and all-released cleanup. Repeated key-down
uses the pinned backend's release/repress behavior; the expected 12 key events
are checked exactly. Browser tests use normal Chromium keyboard input through
the actual PiKVM UI and binary WebSocket transport.

API absolute points produce exact host coordinates `(255,511)`,
`(16383,8191)`, and `(32511,32255)`, then exact left-button press/release.
Further mode-return tests check known coordinates and neutral state. The
frozen host range remains **0..32767**. Browser near-minimum, center and
near-maximum points account for image scaling and rounded letterboxing,
apply the pinned signed API remap, and compare host coordinates within
**one absolute unit**. The report range is unchanged.

Relative API and browser tests verify positive/negative X, positive/negative
Y, diagonal movement, left-button press/release and neutral cleanup. Browser
qualification runs pinned Chromium 145.0.7632.6 under bridge-only Xvfb and uses
native X11 relative motion and Escape. Pointer lock is acquired by a normal
UI click. Browser-observed movement, outgoing upstream binary packet bytes
and host events agree. No synthetic DOM event or alternate transport is used.

The actual mouse-mode radio controls select upstream `usb` and `usb_rel`.
Repeated transitions check the active kvmd state, matching UI state, exact
chosen-device events, silence on the other mouse, and released buttons.
Both functions coexist throughout; mode switching never changes configfs or
descriptors. The workload adds 34 mode transitions, 34 keyboard sequences
and 85 relative-movement checks.

Unauthenticated keyboard, absolute and relative requests return 401; invalid
credentials return 403; authenticated requests produce verified host events.
Logged-out requests return 403 and emit no input. Authentication remains the
unchanged upstream provider/session model, separate from firewall policy.
The server additionally rechecks cookie sessions before every JSON or binary
WebSocket dispatch, closes revoked sockets, and clears HID state on
logout/socket closure. Actual stale JSON/binary attempts produce no host input;
the stale socket reaches CLOSED. Local dispatch tests independently cover
both formats with valid and revoked sessions.

## D9–D10 — reconnect and lifecycle edges

The fresh `direct-reconnect` window began with all interfaces present and both
bridge and target monitors active. `READY TO RECONNECT USB-PC` preceded the
user's unplug/replug. The trace records present → absent → present, unchanged
full USB and HID descriptors, and recovered mappings. All three authenticated
API modes succeeded **before** subsequent browser lifecycle tests; no target
repair was needed. Read-only MSD and moving browser video also passed.

Software rebind stops kvmd, uses the sole owner's unchanged unbind/bind helpers,
reruns identity resolution and starts kvmd. Mapping, descriptors and actual API
input pass afterward. There is no second gadget or concurrent HID writer.

Browser close with Shift held, explicit WebSocket close with Shift held,
logout with Shift/left button held, and kvmd restart with Shift/left button held
all produce host release events. No key/button remains logically stuck.
The tests archive these negative edges, not merely successful HTTP responses.

A kvmd process becoming active precedes HTTP readiness. The measured restart
window includes transient 502s, followed by stale-session denial and successful
normal UI reauthentication. nginx restart also recovers. Subsequent API tests
exercise all three devices; inventories confirm fresh working backends and
exactly one kvmd-owned uStreamer. Planned startup-window proxy errors are
retained; no persistent errors or HID backend errors remain.

## D11 — simultaneous real workload

The unchanged capture contract is MJPEG 1920×1080, V4L2 interval **30/1**,
quality 0 and exactly one kvmd-owned uStreamer. The bridge supplies the accepted
moving-ball HDMI source. All frozen interfaces, including read-only MSD,
remain enumerated.

| Final 120-second measurement | Frames | Delivered fps | Unique hashes | Maximum gap |
| --- | ---: | ---: | ---: | ---: |
| Two-client workload, client 1 | 3573 | 29.772 | 3573 | 0.126 s |
| Two-client workload, client 2 | 3573 | 29.771 | 3573 | 0.123 s |
| Real UI workload, concurrent measured client | 3574 | 29.780 | 3564 | 0.085 s |

The first pair runs alongside 13 complete verified API HID cycles spanning
144.16 seconds. The second workload keeps the actual Web UI video active while
normal browser keyboard and both mouse modes run, plus the measured second
video client. Raw resource samples confirm fan-out and single ownership.
Every complete five-second window changes; the original 120-second, ≥27-fps
and maximum-gap gates are unchanged. No unexpected USB reset, HID write
failure or persistent kvmd/nginx/uStreamer/UVC error occurs in accepted runs.

## D12 — five consecutive clean boots

Every boot repeats policy/TLS probes, authentication, stable mapping and narrow
permissions, actual API input for all three devices, read-only MSD regression,
full browser keyboard/mouse/video/lifecycle tests, API recovery after restart,
and an inventory with no failed systemd units.

| Boot | Immutable run ID |
| --- | --- |
| 1 | `20260907T021946Z-unknown-388565` |
| 2 | `20260907T023234Z-unknown-677965` |
| 3 | `20260907T023515Z-unknown-398715` |
| 4 | `20260907T023757Z-unknown-321825` |
| 5 | `20260907T024038Z-unknown-245573` |

All five have distinct kernel boot IDs and load the same enrolled image,
SHA-256 `d881f1da38c25976b2446ff62d5039e73246b8c78248ab3c4ea7588ea4c98857`.
These are complete RAM boots through the accepted U-Boot/TFTP path; the
known-good SD recovery path and persistent U-Boot environment are unchanged.

## Evidence, reproducibility and retained failures

[Machine-readable acceptance](evidence/m8d-hid.json) and
[selected public evidence](evidence/m8d-hid/) accompany the implementation.
The full 4,877,067-byte archive is on the bridge at
`/home/user/blikvm-hid/m8d-evidence.tar.gz` and the VM at
`out/kvmd-hid/m8d-evidence.tar.gz`, SHA-256
`b4727300566db7334c3c2a8c44489ee44298854c65725e8a969db145abbc77e0`.
Authenticated SFTP transfer matched the hash. All 8,759 archived files passed
an exact qualification-password/private-key-marker scan. Enrolled images,
credentials and private keys are excluded from Git and the evidence archive.

Offline replay verifies **25 API/evdev runs, 615 browser stages, three measured
video clients and five boot records** against raw data. Local validation also
passes 82 tests, Python/JavaScript/shell syntax, per-message revocation checks,
and 337 unchanged inherited runtime files plus frozen M5 helpers/descriptors
and storage bytes. Build/source hashes and dirty-parent provenance are retained. Selected text
exports and two harness files remove trailing whitespace only; the full archive
preserves their tested bytes. Unified-patch context whitespace is retained.

Initial USB enumeration EPROTO failures also reproduced on the exact frozen
M8-C image and remain failed; a later physical intervention restored the path.
Developmental browser failures exposed harness geometry, pointer-lock,
autorepeat and file-handoff assumptions. One developmental video run reported
an invalid JPEG; it remains failed, without a claimed root-cause fix. Later
instrumentation preserves malformed bytes if encountered, and all final
measurements pass the unchanged parser. Helper logout originally invalidated
simultaneous sessions; combined runners now coordinate logout explicitly.
These failures and the pre-exclusion candidate results remain in the archive.
The final five-boot sequence starts after optional delayed-input exclusion.

## Proposed M8-E — not started

Qualify narrowly scoped authenticated **read-only MSD integration** after
establishing backing-store/lifecycle ownership and preserving this HID,
security and video baseline. Define media-selection, authentication,
reconnect and simultaneous-regression gates before implementation.
GPIO/ATX/M6, optional video transports, VNC/IPMI and final read-only-root remain
deferred. No kvmd MSD control is enabled by M8-D.
