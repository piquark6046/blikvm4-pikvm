# Linux 7.x BliKVM bring-up build

The accepted baseline was limited to H616 core support, UART0, and an
Alpine/BusyBox initramfs. Incremental slices now add MMC0/read-only ext4,
EMAC1/RMII, only the USB1 EHCI/PHY/VBUS path wired to the internal MS2131,
and the minimum upstream V4L2/UVC capture stack. The current M5 slice adds
USB0 MUSB peripheral mode and configfs HID keyboard support. OHCI and the
remaining USB controllers, USB audio/host-storage, platform media/codecs,
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

For G3, add `--relative-mouse` to `boot-hid`. This includes the frozen G1/G2
functions and adds only `hid.relative`: three buttons, signed relative X/Y,
no wheel. The descriptor rationale and qualification status are in the
[M5 record](../research/m5-hid-bringup.md). The G1 and G2 command paths remain
available. `G3_RECONNECT_READY` marks the physical USB-PC cable window;
wait at least three seconds before reconnecting firmly. All three evdev
nodes are grabbed during reports. Exact host/target descriptors, function
mapping, input capabilities, signed event order and SYN_REPORT boundaries
are checked before/after rebind and reconnect and during the retained UVC
capture. `--reconnect-evidence` must refer to a passing G3 run with identical
artifact hashes; it never substitutes for the initial physical cable test.

If an otherwise verified G3 physical run stops during concurrent capture,
`python3 lab/relative-live.py --interrupted-run /path/to/run` can requalify
the same already-connected device. It requires the recorded physical
transition and post-reconnect input passes, unchanged tested automation,
matching current USB/evdev identities and exact descriptors, and checks all
three HID paths with another bounded capture. It does not alter binding or
convert the failed run into a pass; two subsequent complete RAM boots are
still mandatory. Every failed attempt remains archived, including any initial
partial UVC frame. Qualification keeps the stricter zero-startup-error gate.

G4 qualification uses `boot-hid --mass-storage`, which retains all three G3
HID functions and adds one 8 MiB disposable FAT16 LUN from the VM-built
initramfs. `build/make-storage-image.py` generates its fixed bytes and manifest;
`gadget-storage setup` verifies the entire image before exposure and configures
`ro=1`, `cdrom=0`, `removable=0`. No vendor SD or host disk backs the LUN.
The only additional kernel options are configfs mass storage and its selected
function driver. The bridge needs `sg3-utils` (including `sg_raw`, `sg_inq`,
`sg_readcap`), the `sg` driver, util-linux, and its existing HID/UVC test tools.

The verifier resolves the disk and SCSI generic device below the identified
composite interface instead of choosing a fixed `/dev/sdX`. It checks all four
interface bindings, exact retained HID descriptors/events, capacity, filesystem
identity, a read-only mount, all known bytes/hashes, rejected filesystem and
SCSI writes, and unchanged full-image hashes. Host image reads use direct I/O
to bypass the page cache. Mounts are removed before software or physical
reconnect. `G4_RECONNECT_READY` opens the cable window; unplug only USB-PC for
at least three seconds. Two later complete RAM-only boots can reference the
passing G4 result with `--reconnect-evidence`; they repeat software rebind,
HID/storage tests and concurrent UVC. See [G4 status and evidence](../research/m5-storage-bringup.md).

G4 is qualified at `linux-7.2.3-usb-gadget-baseline`. The builder also applies
`board/linux-7.2-musb-rx-queue.patch`: MUSB must consume an OUT packet that
arrived before the receive request was queued, rather than flush it. Without
this correction, HID activity can coincide with lost storage commands and
30-second host recovery resets. The verifier rejects unexpected USB resets;
mount/write checks run sequentially, and direct image reads run during UVC.
Failed historical pass flags and the final corrected-kernel acceptance are
preserved in the G4 research record. M6 has not started.
