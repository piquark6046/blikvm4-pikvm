# M8-E authenticated read-only media baseline

Parent: frozen M8-D `ubuntu-26.04.1-kvmd-hid-baseline`.
Read [ownership and the approved eject policy](../../research/m8e-msd-ownership.md).
Accepted at `ubuntu-26.04.1-kvmd-msd-baseline`; see the
[complete qualification record](../../research/m8e-kvmd-msd-bringup.md).

The package layers pinned upstream kvmd 4.213 with M8-A/B/D patches and
`msd.patch`. `function-name.patch` records the independently reviewed E0
adaptation; its changes are already included in `msd.patch`, so do not apply
both when building. No kernel, HID descriptors, video contract, network,
authentication or TLS enrollment changes are included.

`blikvm-gadget.service` retains sole gadget lifecycle ownership. The root
`blikvm-msd-helper.service` delegates only media attachment and eject through a
kvmd-only Unix socket. Its writable configfs mounts are exactly the existing
LUN's `file` and `forced_eject` attributes; the parent configfs mount is
explicitly read-only. It does not write mode flags, UDC,
functions or descriptors. Every operation validates the exact identity,
frozen flags, root-owned approved catalog and full image hash. kvmd remains
unprivileged with no configfs writes, sudo or added block-device privileges.

The one-image static catalog uses the exact frozen G4 bytes under
`/usr/share/kvmd-msd/images`. The original `/usr/share/g4-storage.img` is retained.
At cold boot, the helper validates and adopts only that original known image
before serving requests. Daemon restarts preserve connected media; disconnected
selection is transient. Logout revokes control but leaves media connected.
Eject means empty LUN backing path, MEDIUM NOT PRESENT and rejected direct
reads. Host object disappearance is required on physical USB-PC disconnect.

Only upstream GET `/msd`, POST `/msd/set_params` and `/msd/set_connected` are
registered. Unknown/duplicate parameters and RW/CD-ROM mode fail closed.
Upload, remote media, remove, download and reset routes are absent. The real
UI exposes selection, connection/ejection and state, with excluded controls
hidden and disabled.

Build on the VM:

```sh
mkdir -p out/kvmd-msd
bash build/kvmd-msd/build.sh package
sha256sum out/kvmd-msd/artifacts/kvmd-web_4.213-1blikvm4_arm64.deb > build/kvmd-msd/package.sha256
bash build/kvmd-msd/build.sh rootfs
python3 build/kvmd-msd/check-candidate.py
python3 build/kvmd-msd/check-function-name.py
python3 build/kvmd-msd/check-api.py --source out/kvmd-msd/package-rootfs/build/source
python3 -m unittest discover -s tests
python3 build/kvmd-msd/write-manifest.py
```

Build roots must be fresh; preserve earlier roots and artifacts under distinct
names before repeating builds. Never clean the persistent Linux tree. The
manifest appends the exact existing private M8-C enrollment; enrolled artifacts
and credentials must remain outside Git and public evidence.

Bridge harnesses:

* `msd-hil.py`: direct authenticated API, actual LUN flags/hashes, strict host
  identity, SCSI write protection, negative authorization and optional lifecycle.
* `msd-browser-hil.py`: actual Chromium UI, independent per-stage host checks,
  normal logout, stale WebSocket denial, close/reopen.
* `msd-workload.py`: continuous O_DIRECT full-image hashing during the inherited
  two-client API/HID workload, or `--browser` for the accepted real UI workload.
* `msd-boot-qualification.py`: one complete RAM boot and all E11 gates,
  including actual helper namespace/capability inspection.
* `msd-five-boots.py`: five consecutive full gates, stopping on failure.
* `verify-msd-evidence.py`: independent offline replay of raw host, state,
  protection, video, browser, reconnect and boot evidence.
* `msd-reconnect.py`: monitored physical cable transition, exact USB/HID
  descriptors, actual host object disappearance and restored API/UI operation.

The helper's rejection logs and expected SCSI write/eject errors are evidence,
not reasons to weaken checks. Preserve all failed runs. No writable media,
upload/delete/download, ATX/GPIO or later integration is authorized here.


Replay the full evidence archive from its extracted root:

```sh
python3 lab/verify-msd-evidence.py --root out/kvmd-msd/evidence --output out/kvmd-msd/acceptance-gate.json
python3 lab/msd-audit-archive.py --archive out/kvmd-msd/m8e-evidence.tar.gz --private-dir out/kvmd-lan/private --output out/kvmd-msd/archive-audit.json
```

The tested final directories are `qualification/final-preflight-narrow`,
`qualification/five-boots-narrow` and `qualification/physical-reconnect`.
Earlier development and superseded namespace results remain archived.
