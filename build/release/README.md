# Public release candidate build

The historical `build/image/inputs.lock.json` and accepted artifacts are
unchanged. This path clones a clean commit into a new ignored output directory,
builds from pinned public source and package snapshots, and generates a new
input lock from its own artifacts. It uses `JOBS=2` and never uses the bridge
for ordinary software builds.

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
chain. The repository also has no owner-selected project license, and the
third-party notice inventory remains incomplete. `policy.py` blocks release
publication until those records and exact-byte evidence are added. The
historical P2 image used private recovery-card bootloader bytes and cannot
qualify this new boot chain by association.

To authorize publication later, record the exact source-built bootloader hash
and a real boot evidence file under `research/evidence/` in
`release/qualification.json`. Each entry needs the evidence path and its
SHA-256. A stable image also needs an independently accepted exact public raw
image SHA-256, its bootloader SHA-256, and core-KVM/P2 pass evidence. Beta and
build channels may identify an unqualified image as such, but their bootloader
must still be hardware-qualified. Publication also requires the owner's
project `LICENSE` and a complete `THIRD_PARTY_NOTICES.md`.

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
