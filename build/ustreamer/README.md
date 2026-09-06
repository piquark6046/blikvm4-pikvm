# M7.5 pinned uStreamer derivative (qualified)

Baseline: `ubuntu-26.04.1-ustreamer-baseline`. Full results and preserved
negative attempts are in `research/m75-ustreamer-bringup.md`.

Run on the AMD64 Build VM. M7 remains frozen; this builder verifies and extracts
its accepted tarball into separate trees under `out/ustreamer/`. No kernel or
DTB compilation occurs. All temporary target state remains in RAM.

```
./build/ustreamer/build.sh package
./build/ustreamer/build.sh rootfs
python3 build/ustreamer/write-manifest.py
```

Each phase requires a fresh staging directory (`package-rootfs` or
`rootfs-rootfs`); retain a previous tree under another name before repeating.
Do not delete the persistent Linux build tree. Source download is a fixed commit
archive with mandatory SHA-256, never an arbitrary branch. The separately hashed
`capture-controls.patch` adds an explicit V4L2 device rate and an opt-out of
unsupported JPEG-quality control probing; upstream defaults remain unchanged. The pinned M7
Ubuntu snapshot supplies build and runtime packages. Compilation uses ARM64 GCC
under QEMU inside the existing private user/mount/PID namespace on the VM.
Package assembly uses native AMD64 `dpkg-deb`: it packages ARM64 files without
executing them. `build-packages.tsv` records every build dependency/version;
`packages.tsv` records the installed runtime packages. The manifest records the
builder image, source inputs, baseline and output hashes.

The package contains only uStreamer, its license, a dedicated sysuser, the
identity/capture-specific udev rule, and its service. Optional Python, GPIO,
Janus, V4P and systemd socket activation builds are disabled. No H.264 option is
used. The service uses `--device-fps=30 --desired-fps=30 --quality=0`: upstream
`--desired-fps` alone requests the device maximum and then thins frames.
Native MJPEG is served through `/run/kvmd/ustreamer/ustreamer.sock`; the
runtime directory is owned by `ustreamer` and removed on stop. The service is
ordered after and bound to the udev device alias, with a dedicated udev device group. The unit also declares a cgroup device
allow rule, which needs BPF_SYSCALL support absent from frozen M7; access
control on this kernel is provided by the dedicated account and device mode. A reconnect requests service activation through udev.

`lab/stream-client.py` parses the actual HTTP multipart stream on the bridge,
using authenticated SSH and target curl only to reach the private Unix socket.
It rejects empty/corrupt-marker frames, connection failures, gaps over three
seconds, insufficient frame throughput and any frozen five-second window.
The per-frame JSONL contains elapsed time, length and SHA-256.

After a qualified `lab/ubuntu-boot.py` boot, run as root on the bridge:

```
python3 lab/ustreamer-hil.py --boot-result /path/to/boot.json \
  --out-root /path/to/immutable/runs --seconds 120
```

The runner drives the discovered LattePanda HDMI-A-2 connector with a moving
pattern, exercises stop/start/restart, three real DPMS-off/restoration cycles,
and the frozen M5 keyboard, both mice and RO storage tests during streaming.
Run on a fresh boot because frozen gadget setup rejects an existing gadget.
Use `lab/ustreamer-gate.py` to audit at least two HIL run directories independently.
Inspect full journals and all negative attempts in addition to machine results;
repeat on multiple clean boots before accepting/tagging.
