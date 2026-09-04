# Alpine ARM64 evaluation

**Recommended for initramfs: YES**

**Recommended for final PiKVM image: MAYBE**

Alpine 3.24.1 is the current stable ARM64 release observed on 2026-09-03, and the official 4 MiB `alpine-minirootfs-3.24.1-aarch64.tar.gz` is well suited to a small bring-up environment. Alpine's `mkinitfs` supports building against a staged root and populated `/lib/modules/<kernel-release>`.

## Bring-up initramfs

The first serial-only implementation uses the pinned official minirootfs,
reproducible cpio ordering/ownership/timestamps, a direct `/init`, and a
serial rescue inittab. It intentionally does not configure Linux networking
or add Dropbear until the separate EMAC1 milestone. It passed on real hardware
with Linux 7.2.3 in run `20260904T014648Z-1900fd6-736450`.

Create a pinned builder container and verify the Alpine archive `.sha256` and `.asc`. The image should contain:

- BusyBox/ash, `/init`, devtmpfs/proc/sysfs mounts, and a serial shell;
- `ip`, `udhcpc`, Dropbear, and a lab address only after Ethernet works;
- hardware-specific diagnostic tools only when their separate milestones begin;
- required firmware and modules only when later hardware slices require them;
- a failure shell on every mount/network error rather than an automatic reboot loop.

`/init` should mount pseudo-filesystems, print an artifact/run ID, configure loopback and the lab address, start logging to UART, optionally start Dropbear, run tests, write a result JSON to tmpfs, and remain available for inspection. Build the cpio/gzip output with fixed ownership/timestamps and record its SHA-256.

## Final-image constraints

uStreamer is compatible: upstream documents Alpine packages `libevent-dev`, `libbsd-dev`, `libjpeg-turbo-dev`, `musl-dev` and requires `WITH_PTHREAD_NP=0`.

Current kvmd is less straightforward. Its canonical package and configs assume Python 3.14, systemd services, sysusers/tmpfiles, udev `SYSTEMD_WANTS`, journald, PAM/DBus/systemd Python bindings, and sudo/remount helpers. OpenRC service scripts, device-trigger behavior, logging, dependency packaging, and every native Python extension would need testing. The live board offers only 1 GiB, so Alpine's size benefit is attractive, but it is outweighed during initial porting by the second independent porting problem.

Re-evaluate Alpine after Ubuntu reaches full video/HID/MSD/ATX parity. Promote it to “YES” only if a CI-built musl package set passes the same HIL suite and upstream deltas remain maintainable.
