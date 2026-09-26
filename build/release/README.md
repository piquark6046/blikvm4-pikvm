# Public release candidate build

The historical `build/image/inputs.lock.json` and accepted artifacts are
unchanged. This path clones a clean commit into a new ignored output directory,
builds from pinned public source and package snapshots, and generates a new
input lock from its own artifacts. It uses `JOBS=2` and never uses the bridge
for ordinary software builds.

Offline comparison of the two candidates from Actions run `36236262602`
found 26 differing raw-image bytes, all within the packaged
`/etc/.resolv.conf.systemd-resolved.bak`. That backup contains the individual
runner's temporary DNS configuration. The release-only logging overlay omits
it and records its hash in `file-diff.json`; the release input lock rejects a
rootfs that still contains it. Historical M7 and M8-E artifacts stay frozen.

```sh
JOBS=2 build/release/build.sh --output out/release-local-a
JOBS=2 build/release/build.sh --output out/release-local-b
python3 build/release/compare.py out/release-local-a/public \
  out/release-local-b/public --output out/release-final \
  --tag 1.2.5-beta.2 --commit HEAD
```

Run from a clean, committed checkout. Each output must be new. The two clones
have separate `out/` trees. After recording each artifact, the build removes
only that stage's completed extraction tree. Kernel source and objects remain
through the final kernel delta, then are removed. CI also drops named builder
images after their last use and deletes only intermediate artifacts excluded
from the generated final image lock. `df` and `du` checkpoints are logged. A
five-second `df` sampler records the peak used and minimum free
space in `out/release/disk-samples.tsv` and prints both at exit. The 14-GiB
hosted-runner budget still requires a real runner measurement before claiming
the workflow is release ready.

The source-built U-Boot/TF-A candidate has **no hardware qualification** yet.
`release/qualification.json` contains no newly qualified public image or boot
chain. The owner selected GPL-3.0-or-later for project-authored code and
documentation; the root `LICENSE` contains the GPLv3 text. File-specific SPDX
notices and licenses on third-party source, patches, copied material, and
archived evidence continue to govern those materials. The third-party notice
inventory remains incomplete. `policy.py` blocks release publication until
the remaining records and exact-byte evidence are added. The
historical P2 image used private recovery-card bootloader bytes and cannot
qualify this new boot chain by association.

Pushed `-build.<sha>` tags are candidate-only. CI still runs both independent
builds, compares their bytes, and uploads short-lived candidate artifacts, but
does not create a GitHub Release. The publication policy also rejects manual
attempts to publish build tags. The failed release job in Actions run
`36246591270` is retained as the historical notice-gate result; a new build tag
is needed to verify the candidate-only workflow.

To authorize publication later, record the exact source-built bootloader hash
and a real boot evidence file under `research/evidence/` in
`release/qualification.json`. Each entry needs the evidence path and its
SHA-256. A stable image also needs an independently accepted exact public raw
image SHA-256, its bootloader SHA-256, and core-KVM/P2 pass evidence. A beta
release may identify an unqualified image as such, but its bootloader must
still be hardware-qualified. Publication also requires a complete
`THIRD_PARTY_NOTICES.md`; the project `LICENSE` hash must match the source
manifest generated for the exact release commit.

Bootloader qualification is a separate hardware run. With fresh authorization
for a specifically identified expendable SD card, write the candidate once,
preserve the known-good vendor recovery card, and capture UART/SPL/TF-A/U-Boot
and target boot logs. Prove the source-built boot chain finds the boot script,
loads the exact kernel/DTB, mounts the exact root partition, and survives a
physical reconnect and a second cold boot. Record the boot binary and image
hashes, Git commit, artifact hashes, and both host/target observations in an
immutable evidence namespace. A stable image additionally needs independent
replay of the accepted core-KVM and P2 browser, evdev/SCSI, changing-frame
video, reconnect, and boot gates for that exact image. UART or UDC registration
alone is not qualification. P3, ATX, and RO/overlay remain unaccepted or
deferred until their own contracts are met.
