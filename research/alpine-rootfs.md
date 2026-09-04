# Alpine ARM64 evaluation

**Recommended for initramfs: YES**

**Recommended for final PiKVM image: MAYBE**

Alpine 3.24.1 is the current stable ARM64 release observed on 2026-09-03, and the official 4 MiB `alpine-minirootfs-3.24.1-aarch64.tar.gz` is well suited to a small bring-up environment. Alpine's `mkinitfs` supports building against a staged root and populated `/lib/modules/<kernel-release>`.

## Bring-up initramfs

Create a pinned builder container and verify the Alpine archive `.sha256` and `.asc`. The image should contain:

- BusyBox/ash, `/init`, devtmpfs/proc/sysfs/configfs mounts, and a serial shell;
- `ip`, `udhcpc` or a fixed `192.168.77.2/24` configuration;
- `dropbear` only after Ethernet works, with a build-time public key;
- `dmesg`, `lsusb`, `v4l2-ctl`, `gpioinfo`, `i2cdetect`, `ethtool`, and a JSON test emitter where size permits;
- required firmware and modules, though UART, MMC, EMAC1, and initramfs decompression should initially be built into the kernel;
- a failure shell on every mount/network error rather than an automatic reboot loop.

`/init` should mount pseudo-filesystems, print an artifact/run ID, configure loopback and the lab address, start logging to UART, optionally start Dropbear, run tests, write a result JSON to tmpfs, and remain available for inspection. Build the cpio/gzip output with fixed ownership/timestamps and record its SHA-256.

## Final-image constraints

uStreamer is compatible: upstream documents Alpine packages `libevent-dev`, `libbsd-dev`, `libjpeg-turbo-dev`, `musl-dev` and requires `WITH_PTHREAD_NP=0`.

Current kvmd is less straightforward. Its canonical package and configs assume Python 3.14, systemd services, sysusers/tmpfiles, udev `SYSTEMD_WANTS`, journald, PAM/DBus/systemd Python bindings, and sudo/remount helpers. OpenRC service scripts, device-trigger behavior, logging, dependency packaging, and every native Python extension would need testing. The live board offers only 1 GiB, so Alpine's size benefit is attractive, but it is outweighed during initial porting by the second independent porting problem.

Re-evaluate Alpine after Ubuntu reaches full video/HID/MSD/ATX parity. Promote it to “YES” only if a CI-built musl package set passes the same HIL suite and upstream deltas remain maintainable.

