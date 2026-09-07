# M8-D — qualified authenticated HID

Parent: frozen `ubuntu-26.04.1-kvmd-lan-baseline`. Read
[the ownership decision](../../research/m8d-hid-ownership.md) before deployment.
M6 remains deferred; no kvmd MSD, ATX or GPIO API is installed.

The candidate upgrades the existing `kvmd-web` package to
`4.213-1blikvm3`, retaining pinned upstream 4.213 plus the reviewed M8-A,
M8-B and M8-D patches. It inherits the M8-C rootfs, kernel, network policy,
nginx config, authentication, and unchanged kvmd-owned video configuration.
The exact M8-C enrollment layer is appended without changing certificates,
trust or login credentials. Enrollment is private and must never be archived
as public evidence. The CA private key is never copied.

Additional runtime dependencies from snapshot `20260906T000000Z`:

| Package | Version | Reason |
| --- | --- | --- |
| python3-xlib | 0.33-5 | Upstream HID API keymap import |
| libxkbcommon0 | 1.13.1-1 | Upstream keyboard text conversion import |
| xkb-data | 2.46-2 | Required by libxkbcommon0 |

All inherited runtime versions and these additions are checked against
`packages.lock.tsv`. No X server or GPIO library is added.

Build on the VM:

```sh
bash build/kvmd-hid/build.sh package
sha256sum out/kvmd-hid/artifacts/kvmd-web_4.213-1blikvm3_arm64.deb > build/kvmd-hid/package.sha256
bash build/kvmd-hid/build.sh rootfs
python3 build/kvmd-hid/check-candidate.py
python3 build/kvmd-hid/check-session.py
python3 -m unittest discover -s tests
python3 build/kvmd-hid/write-manifest.py
```

Build roots must be fresh; rename earlier candidate roots to preserve failed
runs before rebuilding. Do not clean the persistent Linux build tree. The
initial wrapper, incorrect Xlib version and missing libxkbcommon failures are
retained under `out/kvmd-hid/`; none was deployed.

`blikvm-gadget.service` starts the frozen M5 helper chain at boot, binds it,
waits for device nodes, and runs `resolve-hid`. The latter verifies function
attributes/descriptors and configfs -> major:minor -> sysfs -> character-node
identity, grants only those nodes to kvmd, and creates stable paths plus
`/run/kvmd-hid/mapping.json`. kvmd cannot write configfs or storage attributes.
Software rebind qualification must stop kvmd, invoke the frozen unbind/bind
helpers, rerun the resolver, and start kvmd. Do not restart the setup oneshot
against an existing gadget: the frozen helper intentionally refuses replacement.

`lab/hid-api-hil.py` is the initial bridge API/evdev harness, not a complete
M8-D acceptance runner. It requires root for EVIOCGRAB and uses authenticated
HTTPS for all reports. Do not run the older M5 direct-write HID harnesses
concurrently with kvmd. D4–D12 browser, negative edges, reconnect, workload
and boot evidence passed; see [the final report](../../research/m8d-kvmd-hid-bringup.md).

The revised direct-input slice deliberately leaves `/hid/print` and
`/hid/events/send_shortcut` unregistered: their optional delayed generation
could outlive logout cleanup. The paste UI remains disabled and macro
record/play transport stays disconnected. All required direct upstream HID
endpoints and JSON/binary events retain their pinned formats.

Browser qualification uses the pinned Chromium 145.0.7632.6 runtime on a
bridge-only Xvfb display. Native `xdotool mousemove_relative` and Escape exercise
normal pointer lock. Bridge test-tool versions are archived separately; they
are not target dependencies. The host harness EVIOCGRABs all three matched
interfaces and temporarily disables/restores repeat on that keyboard only.

The optional `--keep-sessions` on the existing LAN capacity helper is for
combined tests: upstream logout invalidates every session for a user, so the
combined runner controls final logout. The default M8-C helper behavior and
all existing video duration, frame, motion, gap and fps gates remain unchanged.
Malformed JPEG bytes are now retained when the unchanged marker check fails.
