# M8-A video-only kvmd (qualified M8-A)

Build only on the VM. M7.5 is frozen; M6 remains deferred. Never accept this
slice from a successful package build or an API response alone.

`versions.env` pins kvmd v4.213 to the live-rechecked commit and archive digest,
the separately hashed video-only patch, and exact accepted M7.5 rootfs.
`../ubuntu/versions.env` pins the Ubuntu snapshot and builder. No pip dependency
resolution, wheels from moving indexes, or branch downloads are used.

Run `./build/kvmd/build.sh package`, then `./build/kvmd/build.sh rootfs`.
After the rootfs phase, run `python3 build/kvmd/write-manifest.py` to record
source/dirty-state hashes and refresh artifact checksums before transfer.
Each phase requires a fresh staging directory; rename previous staging trees
and retain logs before repeating. Package assembly is native dpkg-deb with
ARM64 metadata and pure Python payload; Ubuntu supplies all required native
extensions. The runtime package inventory records exact versions. No compiler,
GPIO library, nginx, web service or auth backend is required by this variant.

The patch deliberately packages a narrower daemon: the existing kvmd server,
streamer lifecycle, state, snapshots and WebSocket notifications remain, while
excluded integration objects and routes are not constructed. The unused
shared-memory uStreamer binding is imported only by its unused transport.
OCR is explicitly unavailable. System metadata identifies BliKVM; Raspberry Pi
health, fan and extras managers are omitted. Only `/usr/bin/kvmd` is installed
as an entrypoint, with no upstream auxiliary services or privileged helpers.

Ownership is documented with pinned-source evidence in
`research/evidence/m8a-kvmd/ownership.md`. The package stops/disables/masks the
standalone uStreamer service, directs the unchanged video identity rule to
kvmd, and starts the exact frozen uStreamer binary as a kvmd child. Restoring
M7.5 means RAM-booting the accepted artifact; no recovery SD write is needed.

The API socket is `/run/kvmd/api/kvmd.sock`. It is accessed through authenticated
SSH and target-local clients. `lab/kvmd-api.py` tests native routes, JPEG
snapshots, saved snapshot state changes and repeated WebSocket sessions.
`lab/kvmd-hil.py` adds the retained 120-second >=27-fps gate, exact 30-fps V4L2
readback, HDMI loss/recovery, service lifecycle and frozen M5 regressions.
Two fresh package/rootfs builds reproduce identical bytes. Two full HIL boots
followed by three additional clean boot regressions pass; see
[the acceptance record](../../research/m8a-kvmd-video-bringup.md). There is no LAN API, nginx or web UI in this slice.

`lab/kvmd-series.py --root <bridge-work-directory>` runs two full clean-boot
qualifications before three additional 120-second boot regressions. Populate
its `artifacts/` with VM-built payloads and preserve each `runs/` directory.
After authenticated evidence transfer, replay
`python3 lab/kvmd-acceptance-gate.py --root <extracted-evidence>` and
`python3 lab/kvmd-resources.py --root <extracted-evidence>` on the VM.
