# Linux 7.x BliKVM bring-up build

The accepted baseline was limited to H616 core support, UART0, and an
Alpine/BusyBox initramfs. Incremental slices now add MMC0/read-only ext4,
EMAC1/RMII, only the USB1 EHCI/PHY/VBUS path wired to the internal MS2131,
and the minimum upstream V4L2/UVC capture stack. The current M5 slice adds
USB0 MUSB peripheral mode and configfs HID keyboard support. OHCI and the
remaining USB controllers, USB audio/storage, platform media/codecs,
display, and board-control GPIO functions remain disabled.

Build from the repository root:

```bash
./lab/labctl --pretty build-linux
```

The default is `-j3`; override it only when useful with `--jobs N` or
`LABCTL_JOBS=N`. The script never calls `make clean` or `make mrproper`.
Kernel objects and `.config` remain under `out/build/linux-7.2.3/`, and a
no-change rebuild reuses them.

Inputs are pinned in `versions.env`: the kernel.org Linux 7.2.3 archive,
Alpine 3.24.1 ARM64 minirootfs, their SHA-256 digests, and the Debian
bookworm-slim toolchain base digest. Downloads are verified before extraction.
The local toolchain image contains GCC 12.2, the kernel/DT build tools, and
pinned dtschema 2026.6. Every build validates the board DTB with the exact
Linux tree's schemas.

The config starts from `allnoconfig`, not the broad ARM64 defconfig. Its small
set of enabled options was cross-checked against the config embedded in the
known-good vendor 5.19.4 `Image`; the extracted vendor config is retained as
`out/build/vendor-5.19.4.config`. `build/linux-serial.config` is the reviewed
source of truth.

Current artifacts are written to `out/build/artifacts/`. Every `labctl`
build or boot also copies the exact artifacts, hashes, logs, and result JSON
into a unique `out/runs/<run-id>/` directory.

Boot and run the complete retained MMC, Ethernet, and USB-host tests with:

```bash
sudo ./lab/labctl --pretty boot-usb \
  --target-password-file /path/outside/repository/to/vendor-password
```

If the board is already stopped at U-Boot, replace the credential option with
`--no-reboot`. All U-Boot `setenv` operations are session-only. The command
publishes an immutable TFTP run directory, verifies every returned byte count,
captures raw and timestamped UART, waits for `BLIKVM_INITRAMFS_READY`, reruns
the read-only MMC/ext4 and isolated static-Ethernet checks, then archives USB
PHY/controller/VBUS evidence, `lsusb`, `lsusb -t`, VID:PID, topology, speed,
relevant dmesg, and a machine-readable result.

Run the same retained checks followed by UVC binding, complete V4L2 mode
enumeration, and a bounded 60-frame 640x480 YUYV capture with:

```bash
sudo ./lab/labctl --pretty boot-uvc \
  --target-password-file /path/outside/repository/to/vendor-password
```

The initramfs contains a single static `v4l2-test` binary instead of
`v4l-utils`. It uses only the kernel UAPI to enumerate nodes, capabilities,
inputs, standards, formats, sizes and intervals, then performs MMAP streaming
and reports the size, nonzero-byte count and FNV-1a hash of each frame.

The VM/bridge migration passed with direct LattePanda HDMI output connected
to the BliKVM HDMI input; an HDMI dummy plug is not a capture source. See
[migration evidence](../research/vm-bridge-migration.md).

Build the current M5 image on the VM with the same incremental command.
Transfer the artifacts and source snapshot to the bridge, verify their
hashes, and run there:

```bash
sudo ./lab/labctl --pretty boot-hid \
  --artifact-root /path/to/VM-built/artifacts --tftp-root /srv/tftp \
  --target-password-file /path/outside/repository/to/vendor-password
```

The command retains MMC/Ethernet/internal-host tests, validates USB0 UDC and
one keyboard, checks unbind/rebind, then prints `HID_RECONNECT_READY` to
stderr. Unplug/reconnect only USB-PC while that bounded wait is active.
Afterward a bounded Left Shift press/release is verified through the exact
keyboard's evdev input node. The verifier temporarily grabs only that node,
checks both ordered EV_KEY events and synchronization, and releases the
modifier on the target even on a test failure. It repeats this report during
the retained 60-frame UVC capture. The gadget remains bound for inspection.
USB/udev and kernel monitors are archived with host descriptors and input
identity. The report descriptor is also checked through the matching hidraw
node; a successful target write alone is not a pass.

For a second RAM boot with identical artifacts, `--reconnect-evidence`
can reference the first passing boot's `test-results.json`; physical
reconnect is then recorded as previously verified rather than repeated.
Enumeration, unbind/rebind, input press/release, and concurrent UVC are repeated.
For qualification of an already bound keyboard following a separately
monitored physical reconnect, `python3 lab/hid-live.py --reconnect-evidence
/path/to/physical-run/test-results.json` runs the live report/capture checks.
That live check does not substitute for two subsequent complete RAM boots.
This command qualifies only the keyboard slice, not all of M5. The older
`boot-uvc` command deliberately keeps its UVC-only controller expectations;
use archived UVC artifacts with that command and current M5 artifacts with
`boot-hid`.

For G2 (keyboard plus one absolute mouse), build the same incremental image
on the VM and add `--absolute-mouse` to `boot-hid` on the bridge. The separate
`hid-absolute-mouse` helper calls the unchanged G1 setup and adds exactly one
non-boot absolute-pointer function before binding. No reports are sent at
boot or during setup. The reviewed descriptor source is
`initramfs/hid-absolute-mouse.report.hex`; the builder embeds the decoded bytes
in the initramfs.

The G2 runner checks both exact host report descriptors, exactly two usbhid
interfaces, mouse evdev capabilities, and deterministic coordinates/button
reports on grabbed devices. It repeats the input checks after software
rebind, after physical USB-PC reconnect (`G2_RECONNECT_READY`), and alongside
60-frame UVC capture. A prior physical reconnect reference must be from a
passing G2 run with identical artifact hashes. Full qualification additionally
requires two subsequent consecutive RAM-only boots with USB-PC attached.
See [G2 evidence and status](../research/m5-hid-bringup.md).


G2 is qualified at annotated tag `linux-7.2.3-hid-absolute-mouse-baseline`.
If physical handling produces a brief intermediate enumeration that interrupts
post-reconnect testing, preserve the failed boot. The separate
`python3 lab/absolute-live.py --interrupted-run /path/to/run` may qualify the
final already-bound device only when the archived physical sequence, current
identity and exact automation match. It checks actual host events and concurrent
UVC without modifying gadget binding; two subsequent full RAM boots are still
required. See the research record for the accepted evidence chain.
