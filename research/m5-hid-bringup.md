# M5: USB0 UDC and staged HID qualification

Status: G1 keyboard-only and G2 keyboard plus absolute mouse qualification
passed on 2026-09-06. G2 preserves the frozen G1 keyboard unchanged and adds
exactly one absolute-pointer function. Physical reconnect, host evdev input,
concurrent changing UVC capture and two consecutive RAM-only boots are proven.
G3 keyboard plus absolute and relative mouse qualification also passed on
2026-09-06, including physical reconnect and two consecutive RAM-only boots.
Storage remains deferred. This is not completion of all M5.

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

## G2: absolute mouse qualification

G2 retains the G1 keyboard unchanged and adds one reviewed absolute-pointer
report descriptor. Qualification requires exact two-interface host descriptors,
input capabilities and observed events on grabbed devices, software rebind,
physical reconnect, concurrent changing UVC capture and two complete RAM boots.
Relative mouse and disposable read-only storage remain later independent gates.

### G2 descriptor and implementation review

G2 starts at frozen G1 tag `linux-7.2.3-hid-keyboard-baseline`, commit
`6ace5fdbfbe247b1e919dac2e9ba46d6bd9d6fe0`. The entire G1 keyboard helper,
report descriptor, interface subclass/protocol, report length, endpoint
configuration and device strings are unchanged. G2 adds only `hid.absolute`
as interface 1, with subclass/protocol 0/0, one interrupt IN endpoint,
`no_out_endpoint=1`, and a five-byte report without a report ID.
The retained product/serial strings still contain “keyboard”; these are
intentionally stable device identity strings, not an interface count.

The exact 51-byte mouse descriptor is archived in
[`initramfs/hid-absolute-mouse.report.hex`](../initramfs/hid-absolute-mouse.report.hex).
The builder decodes that file into `/usr/share/hid-absolute-mouse.report`;
the target helper copies those bytes to configfs. Each host snapshot saves
both binary and hex copies of each actual HID report descriptor, compares
them byte-for-byte against the source definitions, and saves the USB
descriptor blob and its SHA-256.

| Descriptor bytes | Meaning |
|---|---|
| `05 01 09 02 a1 01 09 01 a1 00` | Generic Desktop Mouse application, Pointer physical collection |
| `05 09 19 01 29 03 15 00 25 01 95 03 75 01 81 02` | Button usages 1–3; logical 0–1; three explicit one-bit data/variable/absolute fields |
| `95 01 75 05 81 01` | Five constant padding bits |
| `05 01 09 30 09 31 15 00 26 ff 7f 75 10 95 02 81 02` | X/Y; logical minimum 0, maximum 32767; two unsigned 16-bit data/variable/absolute fields |
| `c0 c0` | Close both collections |

The report layout is `<BHH` (little endian): three low button bits in byte
0, X in bytes 1–2, Y in bytes 3–4. No wheel, relative axes, feature/output
report or report ID is present. This is the minimal G2 descriptor; final
PiKVM integration has not selected a wheel-bearing descriptor. A local test
independently parses the HID items and verifies their semantics and 40-bit
report length, rather than trusting successful writes.

The deterministic sequence starts from verified zero coordinates/all buttons
released, then sends `(X,Y)=(256,512)`, `(32511,32255)`, `(16384,8192)`, left
button down and up at the intermediate coordinate, and `(0,0)` with all
buttons released. The host verifier requires six ordered EV_SYN report
boundaries with exact expected EV_ABS/EV_KEY values. It rejects missing,
reordered, relative, incorrect, or incomplete events including SYN_DROPPED.
It queries EVIOCGABS and EVIOCGKEY to confirm final neutral state. Both
matching evdev devices are grabbed before any reports or cleanup. The
keyboard retains its G1 Left Shift test.

`labctl boot-hid --absolute-mouse` selects the isolated G2 verifier; the G1
command/verifier remains available without that flag. G2 checks exactly two
usbhid interfaces, exact descriptors, EV_ABS X/Y ranges 0–32767, exactly
BTN_LEFT/BTN_RIGHT/BTN_MIDDLE, and no EV_REL capabilities. It tests both
functions before rebind, after rebind, after physical reconnect, and during
retained 60-frame UVC capture. Two subsequent full RAM boots may reference
the identical-artifact G2 physical reconnect evidence, explicitly recording
that physical unplugging was not repeated on those boots.

### G2 negative evidence

Run `20260906T034645Z-6ace5fd-140145` booted and enumerated both expected
interfaces, exact descriptors and correct mouse input capabilities. It
stopped before functional reports because the verifier incorrectly assumed
one filename per line in BusyBox's terminal `ls` output. The checker now
compares whitespace-separated function names and resolves configfs's relative
symlinks before checking their targets. A fixture rejects missing/extra
functions while accepting columnar output. Neither HID descriptor nor target
artifact changed for this verifier correction. This run is not a G2 pass.

### Initial G2 result: physical reconnect wait expired (superseded below)

VM incremental build `20260906T034430Z-6ace5fd-810002` passed with six jobs.
Image, DTB and kernel configuration retain the G1 hashes in the table above.
Only the initramfs changes: 4,299,100 bytes, SHA-256
`2b18ce4f381cd83c7fb0a193a7c0ca50bc2d26a14285c1bc6e65d25eadb8da08`.
The mouse report descriptor is 51 bytes, SHA-256
`b17306893223490b3e65f4b99477cad3380bcfcb0d3fa2ee0971fbf41e90111a`.
The unchanged keyboard descriptor is 63 bytes, SHA-256
`14bdd69b3b46b4e8a093865c10c75b6a9aaf85f7986f146d87a437e7f7afa476`.

Run `20260906T034809Z-6ace5fd-053056` passed the retained RAM boot,
MMC/read-only ext4, Ethernet and internal MS2131 host checks. Both initial
and post-software-rebind snapshots proved exactly two high-speed usbhid
interfaces, exact descriptors, stable device identity, and expected button
and absolute-axis capabilities. Host evdev confirmed all six ordered mouse
reports and Shift press/release on both passes. Final coordinates and key
states were queried while both devices remained grabbed. Software unbind
removed both target hidg nodes; rebind recreated them and restored configured
UDC state. Host USB device number changed from 19 to 20.

The runner then announced `G2_RECONNECT_READY` and waited 600 seconds.
No physical USB-PC disconnect occurred; it exited at
`hid_physical_reconnect` with `G2 composite did not disconnect`.
This is explicitly **not a G2 pass**. The run did not proceed to post-physical-
reconnect input, concurrent UVC capture, or the two consecutive qualification
boots. Final UART/configfs/dmesg and host evidence were collected; no matching
USB/MUSB/PHY/UDC/HID error lines appeared in the observed logs. That observation
does not substitute for the pending regression gates.

At that point both functions remained bound in neutral/all-released state.
The temporary moving HDMI source was stopped after collection. All 32 local
unit/fixture tests also pass on the bridge. VM and bridge tested automation
bytes match; metadata records G1 parent commit `6ace5fd` plus dirty status
and exact automation hashes.

The byte-exact archive `out/m5/g2-evidence.tar.gz` is 400,133 bytes, SHA-256
`51092e0f6b246b715d6fa63f207809b6c70a576f44f44046610959b2bc53d3b7`.
It contains both negative runs, raw UART/U-Boot, target dmesg/configfs,
host descriptors in binary/hex, evdev event JSON, host kernel/udev logs,
and initial/final tested verifier sources. It was downloaded with an
authenticated, certificate-pinned TLS transfer and its size/hash were
verified against the bridge. Original runs remain at
`/home/user/blikvm-g2/repo/out/runs/`; byte-exact VM copies are under
`out/runs/`. The provisional machine-readable evidence recorded
`not_qualified`, completed checks, source/artifact/evidence hashes,
and the gates still pending at that time. That incomplete attempt was not
committed or tagged; the final qualified archive below supersedes its summary.

### Final physical reconnect and live qualification

The resumed boot `20260906T042537Z-6ace5fd-610854` again passed the retained
stack, initial input and software rebind. During the user-confirmed physical
cable operation, the host recorded device 22 disappearing at 04:26:22.062391,
a brief enumeration as device 23, then another disconnect at 04:26:22.859784.
The verifier attempted its post-reconnect test during that short intermediate
enumeration; the evdev device disappeared and it correctly failed at
`hid_reconnected_input`. No input reports were sent at that failed stage.
This interrupted boot remains failed in the archive.

Final enumeration as device 24 began at 04:26:29.808189: the final disconnected
interval was 6.948405 seconds. Both interfaces bound usbhid, with new evdev
sysfs instances `input35`/`input36`, identical USB and report descriptors,
identity strings, button bits and unsigned absolute-axis ranges.

The separate `lab/absolute-live.py` follow-up does not reboot, set up, unbind
or bind the gadget. It requires an interrupted G2 post-reconnect run, verifies
its automation hashes, archives the full host kernel sequence, checks the
ordered physical removal/enumeration device numbers and at least two seconds
of final disconnection, requires removal of the old evdev objects and a stable
current enumeration, then qualifies the actual final device. It does not
convert the earlier failed boot into a pass or relax the normal boot runner's
requirement for a passing identical-artifact reconnect reference.

Live run `20260906T042917Z-6ace5fd-970522` passed on that final device. Both
grabbed input devices produced the expected ordered reports after reconnect
and during capture, with zero coordinates/all keys and buttons released at
cleanup. The UDC remained configured with precisely the two expected
functions. Its 60-frame MS2131 capture had 49 unique hashes and 48 changing
transitions, with no startup, stream or USB/controller error.

### Two consecutive retained RAM-only boots

With USB-PC continuously attached and identical VM-built artifact hashes,
these two complete boots then passed consecutively:

| Run | Retained stack and HID | Concurrent UVC |
|---|---|---|
| `20260906T043006Z-6ace5fd-692810` | UART/U-Boot/TFTP, MMC/read-only ext4, EMAC1, EHCI1/MS2131, USB0 MUSB, exact two HID interfaces, both input modes before/after rebind and during capture | 60 non-empty frames, 51 unique hashes, 50 changes, zero errors |
| `20260906T043047Z-6ace5fd-858154` | Same complete retained stack and host-event checks | 60 non-empty frames, 56 unique hashes, 55 changes, zero errors |

Each boot references the passing live physical-reconnect qualification with
identical artifact hashes, and explicitly records that physical unplugging
was not repeated on that boot. Both repeat software unbind/rebind, descriptor
and capability inspection, keyboard Shift and absolute coordinate/button
tests, clean configfs/UDC checks, and concurrent UVC capture. All capture
startup/error counts are zero. Host and target logs show no persistent
MUSB/PHY/UDC/USB errors or unexpected USB controller/device resets.

USB descriptor SHA-256 remains
`e4d9234c4ec7594a4581ca2b34471466f81a01b9ee07371a955deaa8392caeb6`
through the physical reconnect, live follow-up and both RAM boots. Host device
numbers progressed to 25/26 then 27/28 across boot/bind/rebind; the stable
serial, product, VID:PID, interface order and descriptor bytes stayed the same.
The kernel, DTB, kernel configuration, G1 helper and G1 report descriptor
remain unchanged from the frozen keyboard baseline.

All 33 local tests pass on both VM and bridge, including the independently
parsed mouse descriptor, capability/interface rejection cases, exact host
event order/cleanup, and interrupted physical-reconnect sequence checks.
The final source archive matches the VM byte-for-byte. Run metadata records
G1 parent revision `6ace5fdbfbe2`, dirty status and automation hashes; the live
runner additionally records its own SHA-256. No later commit is retroactively
attributed to these hardware runs.

### Accepted G2 evidence and next gate

The final byte-exact archive is `out/m5/g2-qualified-evidence.tar.gz`,
1,338,836 bytes, SHA-256
`30de8aafd092e8dfc90829892b6bd0b94bc5884e73b135290d8ce0ebfb101d9b`.
It preserves all three failed attempts, the live follow-up, both passing
boots, original UART/U-Boot and host/target logs, exact binary/hex descriptors,
evdev event JSON, per-run metadata/results and tested sources. Authenticated,
certificate-pinned TLS transfer was verified against the bridge size/hash.
Original runs remain under `/home/user/blikvm-g2/repo/out/runs/`; byte-exact
VM copies are under `out/runs/`. The two passing VM boot directories also
contain the verified VM-built artifacts. Large raw logs/binaries stay out of
Git; the [machine-readable evidence](evidence/m5-g2-absolute-mouse.json)
records `passed`, the exact physical sequence, source/artifact/file hashes,
all HID events and retained checks, UVC summaries, and negative attempts.

The accepted slice is preserved by annotated tag
`linux-7.2.3-hid-absolute-mouse-baseline`. G2 is complete. Both HID functions
remain bound and neutral on the target; the temporary HDMI pattern source
has been stopped. U-Boot and its persistent environment are unchanged; the
vendor SD remains the recovery path.

Proposed G3 only: start from the G2 tag, preserve keyboard and absolute mouse
unchanged, and review/add exactly one relative-pointer HID function with
explicit buttons and deterministic signed relative X/Y ranges. Verify exactly
three usbhid interfaces and their exact descriptors, with EV_REL (not EV_ABS)
on the new evdev device. Grab the matching devices and require ordered positive,
negative and zero-delta/button press-release reports plus neutral cleanup.
Repeat all keyboard/absolute checks, software rebind, physical reconnect,
concurrent 60-frame changing UVC capture and two consecutive RAM-only boots
before accepting a separate relative-mouse baseline. Wheel behavior must be
explicitly reviewed with that descriptor. Mass storage, GPIO/ATX, Ubuntu
rootfs, uStreamer and kvmd remain deferred. G3 has not been implemented.

## G3 descriptor review

G3 starts from frozen G2 `69ddad1` / `linux-7.2.3-hid-absolute-mouse-baseline`.
Before implementing its descriptor, inspected the archived vendor USB-PC
observation and the installed vendor implementation through a `ro,noload`
mount of SD partition 3 (unmounted immediately afterward). Inspection run
`20260906T044828Z-6ace5fd-234925` on the bridge captured
`/mnt/exec/release/lib/hid/enable-gadget.sh`, SHA-256
`f788d87391ded49871b7c02d92327ebace89c966f8c2c2df3a38efaaf7fcb305`.
The bridge inspection runner still used its historical G2 checkout; the
project baseline for the new work is the fetched VM G2 tag above.

`configure_relative_mode` defines eight buttons, signed eight-bit X/Y and
vertical wheel (-127..127), then signed eight-bit Consumer AC Pan. Its
five-byte report and boot-mouse subclass/protocol 1/2 agree with the earlier
host observation. The source's comment beside `95 03` incorrectly says
report count 1; the actual item specifies three axes (X, Y, wheel).
This is captured implementation evidence, not a new vendor-runtime test.

Reviewed `usb-gadget.md`, `pikvm-port.md` and the accepted G2 descriptor
review: the intended port requires independent absolute and relative paths,
configfs function-to-device mapping, and later adaptation to kvmd. G3 chooses
**three buttons, signed eight-bit relative X/Y (-127..127), and no wheel**.
Wheel/pan support is evidenced and useful for eventual scrolling, but is not
needed to qualify the smallest relative movement slice. Adding it now would
expand the exact evdev axis contract and functional tests. As with frozen G2,
this minimal descriptor is not claimed to be wire-compatible with kvmd's
final mouse writer; scrolling and final report-layout adaptation require a
separately reviewed integration change. No existing descriptor changes.

G3's report is three bytes: button bits 0..2 and five constant padding bits,
then signed X and Y. No report ID, wheel, pan, output or feature reports.
The new non-boot interface uses subclass/protocol 0/0 and one interrupt IN
endpoint. Expected host capabilities are exactly BTN_LEFT/RIGHT/MIDDLE and
REL_X/REL_Y, with EV_REL present and EV_ABS absent. Zero relative deltas do
not produce evdev movement or a SYN_REPORT on their own; cleanup must verify
all buttons released and no extra event frame, not invent a neutral event.

The new descriptor is 50 bytes, SHA-256
`58b727cee37368e5916b515aa8cd89e3f0a570e8086d8aa868a154e6d6f87e7e`.
The vendor relative descriptor decoded from the preserved source excerpt is
56 bytes, SHA-256
`ed2b0d7e283a431e6d8441c385d476004df5ce926ae0fb346ee03b9cd82e020a`.
The new helper calls the unchanged G2 helper and adds `hid.relative` before
binding, without sending reports. Mapping checks use each function's `dev`
attribute and `/sys/dev/char`, compare all target descriptor bytes, and require
three distinct character devices. Every host snapshot independently compares
all three report descriptors and USB identity, verifies three usbhid bindings,
and checks exact mouse capability sets. The new relative sequence is
`(+17,0), (-23,0), (0,+31), (0,-47), (-11,+13)`, left press, left release,
then zero delta/all buttons released. Seven exact EV_SYN frames are required;
EVIOCGKEY confirms neutral state while the matching device remains grabbed.

### Proposed G4 (not implemented)

After G3 acceptance, preserve all three HID descriptors and add exactly one
mass-storage function with one disposable backing image built on the VM and
loaded into target RAM. Set `lun.0/ro=1` before binding; use no target SD or
bridge disk as backing storage. Review the MUSB endpoint allocation for the
additional bulk IN/OUT pair. Check exactly three retained HID interfaces plus
one SCSI/Bulk-Only interface, precise host device identity, capacity and write
protection. Read back/hash the complete small image and verify that a bounded
write to this positively identified disposable LUN is rejected and its hash
stays unchanged. Repeat all grabbed HID event tests, software rebind, physical
reconnect, concurrent 60-frame changing UVC with zero errors, and two full
RAM-only boots. No GPIO/ATX, final rootfs, uStreamer or kvmd work is included.

### Initial G3 result: reconnect timeout (superseded below)

At this provisional stage G3 was **not qualified**. VM incremental build
`20260906T045215Z-69ddad1-506697` produced the unchanged G2 kernel,
DTB and configuration hashes. The initramfs is 4,298,420 bytes, SHA-256
`e1122d1e1422c74c6430ff56cb16b8fd0e49807527ba54893e2e4c2f283ee0db`.
An earlier sandboxed build failed before Docker could run because sudo was
blocked by `no_new_privs`; the authorized build reused the persistent objects.
No clean/mrproper operation occurred.

Run `20260906T045426Z-69ddad1-597242` passed the retained RAM boot,
MMC/ext4 read-only, EMAC1 and EHCI1/MS2131 checks. Initial enumeration and
software UDC unbind/rebind each produced exactly three high-speed usbhid
interfaces and matching host/target report descriptors. The function mappings
were keyboard `251:0`, absolute `251:1`, relative `251:2`, resolved through
sysfs rather than assumed from those observed minor numbers. All three input
objects disappeared at software unbind; rebind recreated them as
`input48`, `input49`, `input50` with unchanged identities/capabilities.
USB device number changed from 29 to 30.

Both initial and post-rebind grabbed evdev tests passed: G1 Left Shift
press/release, G2 deterministic absolute coordinates/button test, and the
G3 signed movement/left-button sequence with exact seven SYN_REPORT frames.
All keys/buttons were released and absolute coordinates returned to zero.
The relative node exposed exactly REL_X/REL_Y and BTN_LEFT/RIGHT/MIDDLE,
with no absolute axes, wheels or extra buttons.

The runner announced `G3_RECONNECT_READY` and waited 600 seconds. No physical
USB-PC disconnect was observed; it failed at `hid_physical_reconnect` with
`G3 composite did not disconnect`. This result does not qualify G3. The
post-physical-reconnect tests, concurrent UVC capture, and two consecutive
acceptance boots were not run. No commit, baseline tag or push was performed.
All three functions remain bound and neutral. The temporary HDMI pattern
source was stopped and the bridge restored to VT1. Observed host/target
logs contain no matching USB/MUSB/PHY/UDC/UVC error, but the unperformed
capture and reconnect gates remain required. The archive also retains a
pre-existing host i915 eDP link warning; it is explicitly separated from
USB-controller errors in the machine-readable review.

All 41 local unit/fixture tests passed on VM and bridge. Tested automation,
helpers and descriptors match the VM source byte-for-byte; research/build
README updates were written after testing. The source metadata records G2
parent `69ddad1f2122`, dirty status, and exact automation hashes.
The deployment receiver verified the full bundle size and hash despite curl
reporting a TLS EOF at connection close; the subsequent evidence export used
an explicit HTTP Content-Length and completed without that transport warning.

Byte-exact evidence is retained in `/home/user/blikvm-g3/repo/out/runs/` on
the bridge and `out/runs/` on the VM. Authenticated, certificate-pinned TLS
export `out/m5/g3-evidence.tar.gz` is 288,767 bytes, SHA-256
`74d6f8152ec3ac85bd96fc8552ce0a1db81be3139066710eb37221156736691c`.
It includes UART/raw UART, U-Boot, target configfs/UDC/dmesg, host USB/report
descriptors, evdev events, kernel/udev monitors, metadata/results, tested
sources and the full vendor inspection run. VM run copies also contain the
verified VM-built artifacts. The [machine-readable evidence](evidence/m5-g3-relative-mouse.json)
initially recorded `not_qualified`, passed checks and pending gates; the final
qualified evidence below supersedes that provisional summary.

### G3 resumed run: UART command truncation

Run `20260906T054427Z-69ddad1-137246` passed physical USB-PC reconnect,
exact descriptor/capability recreation, and all three grabbed post-reconnect
input tests. It then captured 60 non-empty frames with 55 unique hashes,
54 changes and zero startup/stream errors, but failed `hid_concurrent_uvc`:
BusyBox's interactive line editor truncated the 2,104-byte UART command,
leaving off its completion marker. The echoed command stops after
`blikvm_rc=$?`; the host correctly timed out instead of accepting the frame
summary alone. This run remains failed.

The G3 host verifier now stages the identical bounded keyboard/absolute/
relative report scripts in `/run` using short base64 chunks and verifies each
script's SHA-256 before execution. The concurrent launch command is short;
the captured report sequences, descriptors, initramfs, kernel, DTB and config
are unchanged. All 42 tests pass locally and on the bridge, including a
fixture checking command bounds and byte-exact script reconstruction.
A new full qualification run repeats the physical test with this corrected
verifier; the original verifier is preserved in the evidence archive.


### Final G3 physical reconnect and live qualification

The corrected boot `20260906T054858Z-69ddad1-234233` recorded USB device 35
removed at 05:50:03.301607 UTC and device 36 enumerating at 05:50:16.280373,
a 12.978766-second physical disconnect. All three old evdev objects disappeared;
the new keyboard, absolute mouse and relative mouse bound usbhid with identical
USB/report descriptors, identity strings and exact capabilities. All three
grabbed input tests passed after reconnect. Its capture delivered 60 valid
changing frames with zero in-stream errors but one flagged partial startup
buffer, so the stricter G3 wrapper correctly kept this boot failed.

Live follow-up `20260906T055156Z-69ddad1-954161` repeated all HID inputs and
capture on the same connected device and also recorded one partial startup
buffer. It remains failed. The retained capture utility explicitly documents
that an isochronous stream may begin partway through its first frame; the
observed buffer was 11,592 bytes versus 614,400 bytes per complete frame.
No kernel USB/UVC/controller error accompanied it, and all 60 subsequent
frames were non-empty and changing. This observation does not erase either
failed attempt or establish that every future stream start will be clean.

The separate `lab/relative-live.py` requires a failed concurrent-capture boot
with proven physical reconnect and all post-reconnect input passes. It checks
unchanged automation hashes, exact USB/report descriptors, the archived
physical transition and removal of all pre-disconnect input objects, current
evdev identities, exact mouse capabilities and target function mappings.
It never reboots, configures, binds or unbinds the gadget. It re-runs all three
grabbed input sequences and concurrent capture, preserving failure status
for all earlier runs. Its own source SHA-256 is recorded in its metadata.

One further bounded live run, `20260906T055323Z-69ddad1-969949`, passed without
changing the acceptance gate: 60 non-empty frames, 60 unique hashes, 59 changes,
zero startup and stream errors, all three expected HID event sequences and
neutral cleanup, exact descriptors/mappings, and no persistent USB/MUSB/PHY/
UDC/UVC error. This is the passing physical-reconnect evidence referenced by
the subsequent complete boots; the cable operation itself is attributed to
the original physical run, not falsely recorded as repeated.

### Two consecutive G3 RAM-only boots and accepted evidence

With USB-PC left attached and identical VM-built artifacts, the following
full boots passed consecutively without any intervening failed boot:

| Run | Retained stack and HID | Concurrent MS2131 capture |
|---|---|---|
| `20260906T055434Z-69ddad1-749933` | UART/U-Boot/TFTP, MMC/ext4 read-only, EMAC1, EHCI1/MS2131, USB0 MUSB, keyboard, absolute and relative mouse; exact descriptors/capabilities/mapping and software rebind | 60 non-empty frames, 60 unique hashes, 59 changes, zero startup/stream errors |
| `20260906T055522Z-69ddad1-090548` | Same complete retained stack and all three grabbed input tests | 60 non-empty frames, 60 unique hashes, 59 changes, zero startup/stream errors |

Each boot verified keyboard Shift press/release, the frozen absolute coordinate
and button sequence, and signed relative X/Y movement plus button press/release
before/after rebind, after validating the prior physical evidence, and during
capture. Function mappings remained keyboard `251:0`, absolute `251:1`,
relative `251:2`, always derived from configfs `dev` and sysfs. All functions
stayed bound through capture. Neither boot contains a persistent USB/MUSB/PHY/
UDC/UVC error or unexpected USB/controller reset. All 42 local tests pass on
both VM and bridge; the tested executable sources and descriptors match the VM
byte-for-byte. Research documentation was finalized after testing.

The final byte-exact archive `out/m5/g3-qualified-evidence.tar.gz` is
1,688,086 bytes, SHA-256
`cb720638edf1ffa9ce27bd4523b7202db2fa9adb1cbd617e14594c698fc9477a`.
It preserves all failed attempts, the passing live follow-up, both full boots,
UART/raw UART, U-Boot/TFTP, target dmesg/UDC/configfs state, host kernel/udev
monitors, exact USB/HID descriptors, evdev events, capture records, metadata,
current and initial verifier sources, and vendor descriptor inspection.
Authenticated certificate-pinned TLS transfer was checked against bridge
size/hash. Original runs remain in `/home/user/blikvm-g3/repo/out/runs/`;
byte-exact VM copies are under `out/runs/`, with verified VM-built artifacts
added to each passing run. Large raw logs and binaries remain outside Git.
[Machine-readable evidence](evidence/m5-g3-relative-mouse.json) now records
`passed`, source/artifact/file hashes, physical provenance, all host events,
retained checks and negative attempts. Runs identify G2 parent `69ddad1f2122`
plus dirty status; no later commit is retroactively attributed to hardware.

G3 is qualified at annotated tag
`linux-7.2.3-hid-relative-mouse-baseline`. The G1 and G2 helpers/descriptors,
kernel, DTB and config remain unchanged. Three HID functions remain bound
and neutral; the temporary HDMI source has been stopped and the bridge
returned to VT1. The vendor SD and persistent U-Boot environment are unchanged.
Work stops before G4; the proposed read-only mass-storage plan above remains
unimplemented, as do GPIO/ATX, Ubuntu final rootfs, uStreamer and kvmd.
