# Ubuntu 26.04 ARM64 root filesystem

Recommendation: use the official **Ubuntu Base 26.04.1 LTS (Resolute) ARM64** tarball, not a Raspberry Pi preinstalled image. As of 2026-09-03 the official file is `ubuntu-base-26.04.1-base-arm64.tar.gz`; its published SHA-256 is `5a1906794ced63a71a8119c3f211ef5f0bbe0a243001b4bbd41fdf80c5b219fd`. Pin the filename, checksum file, and signature in build metadata rather than silently following “latest.”

## Reproducible build design

1. Run a pinned Fedora/Ubuntu container definition from the AMD64 host. Install `qemu-user-static`/binfmt only for ARM64 maintainer scripts that must execute; prefer package extraction/configuration tools that minimize emulation.
2. Download Ubuntu Base, `SHA256SUMS`, and `SHA256SUMS.gpg` from Canonical. Verify both signature and archive hash before extraction.
3. Extract as root with numeric owners into a fresh staging directory. Bind/mount `proc`, `sys`, `dev`, and `dev/pts` only inside the build container/chroot and unmount them on every exit path.
4. Configure `ports.ubuntu.com` for `resolute`, `resolute-updates`, and security; set locale, UTC default, hostname, machine-id first-boot handling, and predictable interface naming.
5. Install a minimal base: `systemd-sysv`, `udev`, `kmod`, `initramfs-tools`, `iproute2`, `ethtool`, `openssh-server`, `ca-certificates`, `sudo`, `rsync`, `curl`, `usbutils`, `v4l-utils`, `i2c-tools`, `libgpiod-tools`, and diagnostics. Keep recommends disabled unless justified.
6. Use `systemd-networkd` for the first image. Ship a static lab profile for `192.168.77.2/24` with no default gateway, plus an opt-in DHCP profile for later deployments. NetworkManager adds no value to early bring-up.
7. Provision SSH with a build-time public-key file that is deliberately outside Git. Disable password and root password login. Never bake the vendor default password or a private key into an image.
8. Install pinned kernel modules under `/lib/modules/<release>`, place `Image`, DTB, and initramfs in a separate artifact directory, and run `depmod`/`update-initramfs` under ARM64 emulation if required.
9. Build uStreamer and kvmd as explicit versioned packages. Do not let the rootfs build install arbitrary Git `master` or unpinned pip dependencies.
10. Emit a deterministic tarball and/or ext4 filesystem plus manifest: source URLs/hashes, package versions, file hash, build tool image digest, Git revisions, and `SOURCE_DATE_EPOCH`.

A native ARM64 container invocation (`podman run --platform linux/arm64`) may work through registered binfmt, but the builder must test for binfmt first and fail clearly. A two-stage `debootstrap --foreign` is an alternative; Ubuntu Base is simpler because Canonical already publishes the board-independent filesystem.

## PiKVM package layers

- Base/diagnostic layer: systemd, SSH, networking, udev, kmod, V4L2, USB and GPIO tools.
- Video layer: uStreamer build deps (`libevent-dev`, `libjpeg-dev`, `libbsd-dev`, optionally libgpiod/systemd), runtime libraries, service user and Unix socket.
- kvmd layer: Python 3.14 and the translated v4.213 PKGBUILD dependencies, nginx, PAM, DBus, libgpiod v2, services/tmpfiles/sysusers, configs and web assets.
- Optional layer: Janus/H.264, VNC, IPMI, NBD, OLED/LCD, certbot, Wi-Fi/BT.

Build the minimal feature set first so missing optional Python modules cannot hide core bring-up failures.

## Storage and read-only policy

Start read-write during porting. Once stable, make the OS partition read-only, put `/var/lib/kvmd`, uploaded images, SSH host keys, logs/metrics, and update state on a dedicated writable partition or overlay. Preserve the vendor image's good power-loss property without copying its opaque `/mnt` layout. MSD backing files must never be mounted writable locally while exported writable to the controlled host.

