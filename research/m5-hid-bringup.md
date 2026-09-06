# M5: USB0 UDC and one HID keyboard

Status: G1 keyboard-only qualification passed on 2026-09-06. Physical
USB-PC reconnect, host input press/release, concurrent changing UVC capture,
and two subsequent consecutive RAM-only boots all passed. The remaining M5
mouse and storage gates are not accepted or implemented.

## Prerequisite

The VM/bridge migration passed `boot-uvc` in run
`20260906T024143Z-8cd48fc-903152`: 60 frames, 60 unique hashes, no stream
errors, with retained serial/MMC/Ethernet/USB checks. The HDMI source must
connect directly from the LattePanda to BliKVM HDMI input. The earlier dummy
plug produced a frozen capture and was removed by the user.

## Minimal implementation

The board DTS enables only `usbotg` in peripheral mode. Its inherited H616
description supplies PHY0, clock/reset, IRQ and extcon, matching the vendor
wiring evidence. USB1 EHCI/PHY1/PC8-controlled VBUS remains unchanged. No USB0
VBUS output supply or new carrier GPIO is invented.

The incremental kernel configuration adds MUSB gadget-only mode, the sunxi
glue, NOP transceiver, configfs/libcomposite and HID. MUSB host/dual-role,
OHCI, gadget storage, audio and the other gadget functions remain disabled.
The kernel suffix is `-blikvm-v4-hid`.

The initramfs `hid-keyboard` utility creates a RAM-only configfs gadget;
it does not bind or send reports at boot. It identifies the single UDC by
its USB0 sysfs parent instead of hard-coding the dynamic instance suffix.
The observed upstream UDC is `musb-hdrc.1.auto`, parent `5100000.usb`.

The gadget uses one boot-keyboard interface, an eight-byte report, a standard
63-byte report descriptor, one interrupt IN endpoint, VID:PID `1d6b:0106`,
product `BliKVM M5 keyboard`, and serial `blikvm-v4-m5-keyboard`. There is no
mouse or storage function. The neutral report contains eight zero bytes
(all keys released). Its target node is resolved through the function's
`dev` attribute; `/dev/hidg0` ordering is not assumed.

`labctl boot-hid` retains prior regressions and permits exactly the expected
MUSB controller alongside EHCI1. The older `boot-uvc` controller check remains
strict and should use archived UVC-only artifacts. `lab/hidlab.py` validates
the host identity, exactly one keyboard interface, usbhid binding, high-speed
connection, and the host's exact cached report descriptor. It checks actual
host disappearance/reappearance for unbind/rebind and physical reconnect.
After physical reconnect, it checks an ordered Left Shift press/release
through the matching evdev input node, including EV_SYN boundaries. The
node is temporarily grabbed so the test modifier stays private to the
verifier. Target writes are bounded and include an all-released cleanup.
The same input check runs during the retained 60-frame UVC capture. A
successful write or neutral hidraw report alone does not qualify G1.

Subsequent boots may reference a prior passing reconnect report, but only for
identical artifact hashes. It repeats enumeration/rebind/report/UVC. The
result records that the physical reconnect was not repeated on that boot.
This is keyboard-slice qualification, not completion of all M5 gates.

## Builds and initial hardware results

Both builds use the VM's persistent Linux build directory with six jobs:

- `20260906T024436Z-9edcd3a-507458`: kernel/DT/config and initial helper build.
- `20260906T025601Z-9edcd3a-802921`: helper correction; same kernel/DT/config.

The current artifacts are:

| Artifact | Size | SHA-256 |
|---|---:|---|
| Image | 6,291,464 | `dce17c18ba67a8bb227b5dd6573aa4ebd38c6b347fa24b18ecb3ca8c9ccbaa04` |
| DTB | 20,580 | `3dadd0efd2c9ded33d852446a32e9cd2de2a6989c1f01798c1ab3c6f49887ee2` |
| initramfs | 4,298,923 | `b2e7bd1e18493a15a684b4fb590c1601d45bad249756ecedd125ccfa4409bc3b` |
| config | 65,127 | `2067d71d941c0748ec0739b849635805534e945d87d271b53b3a9673c31b8dad` |

Run `20260906T025503Z-9edcd3a-467325` passed UDC registration and real host
enumeration: high speed, configured state, one boot keyboard. Unbind removed
the host device and target character node correctly, but the helper's state
collector incorrectly failed on the absent node. The helper now tolerates
absent character nodes during unbound-state inspection.

Run `20260906T025705Z-9edcd3a-483387` then successfully rebound the device,
but an asynchronous kernel GPIO-base deprecation printk split the beginning
of the UART transaction marker. The host runner now temporarily suppresses
console printk during gadget transactions, as the retained UVC runner does,
while collecting full dmesg afterward. It does not relax marker matching.

Run `20260906T025815Z-9edcd3a-464928` reached the physical reconnect wait
after passing enumeration and unbind/rebind. Its five-minute wait expired
without a host disconnect, so it stopped at `hid_physical_reconnect` and did
not send an input report or run concurrent UVC. The keyboard remains bound
on the target; the temporary HDMI source has been stopped. All 24 current
local fixture tests pass. This was the provisional state before the G1 qualification below. Mouse
and storage functions have not been added.

Original hardware evidence is under `/home/user/blikvm-m5/repo/out/runs/`
on the bridge. Run metadata records source commit, dirty status and hashes
of the automation scripts. VM build artifacts originate only from the VM.
Selected original-run text evidence, including UART, U-Boot, target state,
host descriptors/dmesg, and result JSON, is downloaded via SFTP under
`out/m5/bridge-runs/` on the VM. These local text copies retain connector
redactions; byte-exact originals remain on the bridge.
Deployment used SFTP for setup and authenticated HTTPS with a pinned
certificate, one-request receiver, fixed destination, size and SHA-256 check
for the binary bundle. Plain HTTP was rejected and not used for this M5
transfer. Credentials and transfer keys remain outside tracked files.


## G1 qualification: 2026-09-06

The user physically unplugged only USB-PC, leaving power, UART and Ethernet
connected. The live monitor had already archived host lsusb/tree, full USB
and HID report descriptors, and the exact evdev identity, with udev and kernel
monitors running. Run `20260906T032328Z-9edcd3a-632784` recorded:

- USB device 12 removed at 03:27:57 UTC; the host lsusb snapshot no longer
  contained the keyboard and its old input sysfs object disappeared.
- USB device 13 enumerated at 03:28:08 UTC, on the same port at 480 Mb/s,
  with identical USB and report descriptors, VID:PID `1d6b:0106`, product
  and serial, and one boot-keyboard interface bound to `usbhid`.
- Input instance `input17` was replaced by `input18`, with the same name,
  vendor/product, physical path, serial and key capabilities. Linux reused
  `/dev/input/event10`; recreation is proved by the changed sysfs instance,
  not by requiring a different event-number allocation.
- No host USB/HID error appeared in the live reconnect kernel log.

The live follow-up `20260906T032847Z-9edcd3a-824830` verified target UDC
configured state and `KEY_LEFTSHIFT` (EV_KEY code 42) value 1 then value 0
on that exact host input device. It repeated the press/release concurrently
with a retained 60-frame MS2131 capture. All 60 frames were non-empty, all
60 hashes differed, and all 59 adjacent transitions changed. There were no
startup/error frames or persistent USB/MUSB/PHY/UDC/UVC errors.

With USB-PC remaining attached, the following two RAM-only boots then passed
consecutively, using the identical VM-built artifact hashes listed above:

| Run | Retained stack | Input events | Concurrent capture |
|---|---|---|---|
| `20260906T033008Z-9edcd3a-215238` | UART, U-Boot, TFTP, MMC/ext4, EMAC1, EHCI1/MS2131, USB0 UDC, HID | Shift press/release before and during capture | 60 non-empty frames, 60 unique hashes, 59 changes, zero errors |
| `20260906T033114Z-9edcd3a-029399` | Same complete retained stack | Same verified input checks | Same passing frame counts and zero errors |

Each boot includes software unbind/rebind, exact HID report-descriptor
validation, host descriptors/lsusb/tree, udev/kernel monitoring, target
UDC/configfs state and dmesg. Both mount ext4 with `ro,noload`, read
`/etc/os-release`, unmount, and confirm block-device read-only state. EMAC1
uses the retained isolated static lab link. U-Boot is unchanged and its
environment is not saved; the vendor SD remains the recovery path.
The direct LattePanda HDMI source was a moving GStreamer ball pattern at
1280x720/30 through connector 287; capture negotiated YUYV 640x480/30.
Each capture consumed 36,864,000 bytes while the keyboard remained bound.

All 26 local unit/fixture tests passed, including rejection of release-only,
press-only, reversed, repeated and wrong-key input sequences and truncated
input records. Tested bridge automation matches the VM source byte for byte.
No target artifact needed rebuilding for these host-verifier changes.
An initial boot-command invocation lost its executable bit during SFTP upload
and failed before running; invoking `python3 lab/labctl` resolved that bridge
launch issue. It did not reboot the target or interrupt the two-boot sequence.
An earlier monitor preparation was stopped before announcing the live window;
it is not counted as a physical test or a passing run.

## Evidence and baseline

Byte-exact evidence is retained in normal `out/runs/<run-id>/` directories
on both the VM and `/home/user/blikvm-m5/repo` on the bridge. The VM's two
qualification directories also contain the verified build artifacts. Original
UART/raw UART, U-Boot, target/controller state, evdev events, host descriptors,
udev events and kernel logs are preserved. The earlier selected SFTP copies
had connector redactions; the G1 archive was transferred without redaction
using the existing authenticated, certificate-pinned, one-request TLS channel.

The archive `out/m5/g1-evidence.tar.gz` is 1,002,985 bytes with SHA-256
`ddece07d55d2fe87c9853b0709d16fdcbb71de7e592628aef04597fd4b071e99`.
It includes the exact live reconnect script and tested host/helper sources.
[The checked-in machine-readable evidence](evidence/m5-g1-keyboard.json)
preserves the qualification results, input events, physical reconnect kernel
log, artifact hashes, and per-file evidence hashes. Full raw logs and binaries
remain outside Git. All hardware runs record parent revision `9edcd3a` with
a dirty source tree; automation hashes identify the tested changes rather
than falsely attributing the later commit to earlier runs.

The verified keyboard-only slice is preserved by the annotated tag
`linux-7.2.3-hid-keyboard-baseline`. G1 is complete; work stops here.

## Proposed G2: absolute mouse, not yet started

Start from the G1 tag and retain the keyboard unchanged. Review one absolute
pointer report descriptor with explicit button bits and unsigned X/Y logical
ranges. Add only that one configfs HID function in a separate RAM-only slice.
Verify the host's exact two-interface descriptors, HID bindings, input
identities and absolute-axis ranges. Use a grabbed input device to validate
bounded deterministic coordinates and button press/release without moving
the host's active pointer. Repeat unbind/rebind and physical reconnect, retain
the keyboard input checks and simultaneous 60-frame changing UVC capture,
and reproduce the full stack across two RAM-only boots before accepting G2.
Relative mouse and disposable read-only storage remain later independent
gates; GPIO/ATX, Ubuntu rootfs, uStreamer and kvmd remain deferred.
