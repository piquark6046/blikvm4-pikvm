# PiKVM userspace portability

Upstream snapshots inspected on 2026-09-03:

- `pikvm/kvmd` v4.213, commit `387846d22fa807f97de09750c32c1c9b26d36c1c`.
- `pikvm/ustreamer`, commit `3af6bfac0f11dddd7e743e914705a6b0c58eb9e4`.

PiKVM upstream explicitly permits non-Raspberry-Pi boards but does not ship an image for them; it expects the porter to supply the OS and replace board-specific configuration and udev rules. PiKVM OS itself is an Arch Linux ARM image and its packaging is not a portable board abstraction.

## Runtime component map

| Component | Portable core | Port work for BliKVM |
|---|---|---|
| `kvmd` | Python 3.14 daemon and WebSocket/HTTP API | Package the large Python/native dependency set; create a BliKVM platform YAML; disable Raspberry Pi health/boot assumptions |
| uStreamer | V4L2 MJPEG streamer; explicitly builds on Debian/Ubuntu and Alpine | Point at stable `/dev/kvmd-video`, use MJPEG pass-through, test signal reset; omit Janus/H.264 initially |
| Web UI/nginx | Static UI and nginx proxy to Unix sockets | Preserve `/etc/kvmd`, `/run/kvmd`, permissions, certificate and socket layout |
| Authentication | PAM/passlib/bcrypt/htpasswd paths | Map Ubuntu PAM modules and service users; provision unique credentials out of tree |
| HID | Configfs gadget plus `/dev/hidg*` | Bli udev rules for keyboard/absolute/relative mouse; use H616 MUSB UDC name dynamically |
| MSD | Configfs mass storage and remount helpers | Dedicated image filesystem; narrowly scoped sudo helpers; safe read-only default |
| ATX/GPIO | Current kvmd uses libgpiod v2 for ATX and user GPIO | Use the H/I bank chip and offsets or line names; validate polarities; never use vendor sysfs global numbers as an API |
| Service management | Upstream ships many systemd units, sysusers/tmpfiles, udev `SYSTEMD_WANTS` rules | Ubuntu aligns well; Alpine would need an OpenRC/udev lifecycle port |
| Optional services | Janus, VNC, IPMI, OLED, NBD, certbot | Exclude from first image; add after core KVM passes |

The current `kvmd` PKGBUILD pins Python `>=3.14,<3.15`, libgpiod `>=2.1`, uStreamer `>=6.47`, v4l-utils, nginx, systemd/PAM/DBus bindings, and many optional Python integrations. `setup.py` does not carry `install_requires`, so blindly running `pip install .` produces an incomplete system. Treat the PKGBUILD and service/config trees as the dependency manifest, then translate them into a versioned Debian package or reproducible staged rootfs.

The community `RainCat1998/Bli-PiKVM` port is useful evidence that kvmd can run on this class of board, but it patches a much older kvmd, uses broad sudo rules, and reports GPIO ownership conflicts with the vendor daemon. It is not a production base.

## Ubuntu 26.04 ARM64 feasibility

**Recommended.** Ubuntu 26.04 supplies the Python 3.14 ABI current kvmd requests, systemd/udev, nginx, PAM, DBus, libgpiod, V4L2, and conventional Debian build tooling. The live vendor image is already Ubuntu/Armbian with systemd, reducing operational surprises.

Work remains: translate Arch package names, build missing Python wheels/native modules for ARM64, package uStreamer, adapt services and udev rules, create a Bli platform config, and test each optional plugin import. This is packaging/configuration work rather than an architectural rewrite.

## Alpine ARM64 feasibility

**Technically plausible, not first.** uStreamer explicitly documents Alpine dependencies and `WITH_PTHREAD_NP=0`, so video is viable. The hard part is kvmd's service environment: current upstream assumes systemd units, systemd-triggered udev rules, journald/sysusers/tmpfiles behavior, Python systemd/PAM/DBus modules, and helper paths. Alpine/musl/OpenRC would need a maintained compatibility layer and a separately validated package matrix. That effort does not help prove the board.

## Recommended port order

1. On minimal initramfs, prove kernel, SD, EMAC1, USB host/UVC, UDC, and GPIO reads.
2. Build Ubuntu Base with systemd-networkd and SSH.
3. Package uStreamer alone and validate 1080p30 MJPEG/reconnect.
4. Package minimal kvmd + nginx/auth with video only.
5. Add HID, then MSD, then ATX with constrained permissions.
6. Add optional services and read-only-root policy last.

