#!/bin/bash
set -euo pipefail
umask 022

repo=/work
source "$repo/build/versions.env"

jobs=${JOBS:-3}
case "$jobs" in
    ''|*[!0-9]*) echo "JOBS must be a positive integer" >&2; exit 2 ;;
    0) echo "JOBS must be greater than zero" >&2; exit 2 ;;
esac

linux_src="$repo/out/src/linux-$LINUX_VERSION"
linux_build="$repo/out/build/linux-$LINUX_VERSION"
artifacts="$repo/out/build/artifacts"
board_dts=sun50i-h616-blikvm-v4.dts
board_dtb=sun50i-h616-blikvm-v4.dtb

test -f "$linux_src/Makefile"
mkdir -p "$linux_build" "$artifacts"
kernel_dts="$linux_src/arch/arm64/boot/dts/allwinner/$board_dts"
if ! cmp -s "$repo/board/$board_dts" "$kernel_dts"; then
    install -m 0644 "$repo/board/$board_dts" "$kernel_dts"
fi
if ! grep -q 'blicube,blikvm-v4' \
    "$linux_src/Documentation/devicetree/bindings/arm/sunxi.yaml"; then
    patch -d "$linux_src" -p1 < "$repo/board/linux-7.2-bli-v4.patch"
fi
if ! grep -q 'compatible = "allwinner,sun50i-h616-emac"' \
    "$linux_src/drivers/net/ethernet/stmicro/stmmac/dwmac-sun8i.c"; then
    patch -d "$linux_src" -p1 < "$repo/board/linux-7.2-h616-emac1.patch"
fi

config_hash=$(sha256sum "$repo/build/linux-serial.config" | cut -d' ' -f1)
if ! test -f "$linux_build/.config" \
   || ! test -f "$linux_build/.config-input.sha256" \
   || test "$(cat "$linux_build/.config-input.sha256")" != "$config_hash"; then
    make -C "$linux_src" O="$linux_build" \
        KCONFIG_ALLCONFIG="$repo/build/linux-serial.config" allnoconfig
    printf '%s\n' "$config_hash" > "$linux_build/.config-input.sha256"
else
    make -C "$linux_src" O="$linux_build" olddefconfig
fi

required_symbols='ARCH_SUNXI BLK_DEV_INITRD RD_GZIP BINFMT_ELF BINFMT_SCRIPT DEVTMPFS DEVTMPFS_MOUNT SERIAL_8250 SERIAL_8250_CONSOLE SERIAL_8250_DW SERIAL_OF_PLATFORM PINCTRL_SUN50I_H616 DMA_SUN6I SUN50I_H616_CCU TMPFS PRINTK_TIME MAGIC_SYSRQ_SERIAL POSIX_TIMERS BLOCK PARTITION_ADVANCED MSDOS_PARTITION MMC MMC_BLOCK MMC_SUNXI REGULATOR REGULATOR_FIXED_VOLTAGE EXT4_FS NET PACKET INET ETHTOOL_NETLINK NETDEVICES ETHERNET NET_VENDOR_STMICRO STMMAC_ETH STMMAC_PLATFORM DWMAC_SUN8I PHYLIB FWNODE_MDIO OF_MDIO MDIO_BUS_MUX USB USB_ANNOUNCE_NEW_DEVICES USB_EHCI_HCD USB_EHCI_HCD_PLATFORM EXTCON POWER_SUPPLY GENERIC_PHY PHY_SUN4I_USB MEDIA_SUPPORT MEDIA_SUPPORT_FILTER MEDIA_CAMERA_SUPPORT MEDIA_USB_SUPPORT VIDEO_DEV MEDIA_CONTROLLER USB_VIDEO_CLASS VIDEOBUF2_CORE VIDEOBUF2_V4L2 VIDEOBUF2_MEMOPS VIDEOBUF2_VMALLOC'
required_symbols="$required_symbols USB_GADGET USB_MUSB_HDRC USB_MUSB_GADGET USB_MUSB_SUNXI NOP_USB_XCEIV USB_LIBCOMPOSITE CONFIGFS_FS USB_CONFIGFS USB_CONFIGFS_F_HID"
for symbol in $required_symbols; do
    if ! grep -qx "CONFIG_${symbol}=y" "$linux_build/.config"; then
        echo "required CONFIG_${symbol}=y was not resolved" >&2
        exit 1
    fi
done

for symbol in USB_OHCI_HCD USB_MUSB_HOST USB_MUSB_DUAL_ROLE USB_CONFIGFS_MASS_STORAGE SND SND_USB_AUDIO DRM MEDIA_PLATFORM_SUPPORT VIDEO_SUNXI_CEDRUS MEDIA_ANALOG_TV_SUPPORT MEDIA_DIGITAL_TV_SUPPORT MEDIA_RADIO_SUPPORT MEDIA_SDR_SUPPORT MEDIA_TEST_SUPPORT; do
    if grep -Eq "^CONFIG_${symbol}=(y|m)$" "$linux_build/.config"; then
        echo "forbidden HID keyboard slice CONFIG_${symbol} is enabled" >&2
        exit 1
    fi
done

make -C "$linux_src" O="$linux_build" -j"$jobs" Image
make -C "$linux_src" O="$linux_build" -j"$jobs" \
    "allwinner/$board_dtb"
make -C "$linux_src" O="$linux_build" -j"$jobs" CHECK_DTBS=y \
    "allwinner/$board_dtb"

install -m 0644 "$linux_build/arch/arm64/boot/Image" "$artifacts/Image"
install -m 0644 \
    "$linux_build/arch/arm64/boot/dts/allwinner/$board_dtb" \
    "$artifacts/$board_dtb"
install -m 0644 "$linux_build/.config" "$artifacts/linux.config"

alpine_tar="$repo/out/downloads/alpine-minirootfs-$ALPINE_VERSION-aarch64.tar.gz"
printf '%s  %s\n' "$ALPINE_SHA256" "$alpine_tar" | sha256sum -c -

staging=$(mktemp -d "$repo/out/build/.initramfs.XXXXXX")
trap 'rm -rf "$staging"' EXIT
# GNU tar otherwise applies the caller's umask for an unprivileged extraction.
# Preserve the pinned archive modes explicitly so the generated cpio is stable
# whether labctl itself was invoked directly or through sudo.
tar -C "$staging" --no-same-owner --same-permissions -xzf "$alpine_tar"
install -m 0755 "$repo/initramfs/init" "$staging/init"
install -m 0644 "$repo/initramfs/inittab" "$staging/etc/inittab"
install -m 0755 "$repo/initramfs/lsblk" "$staging/usr/bin/lsblk"
install -m 0755 "$repo/initramfs/lsusb" "$staging/usr/bin/lsusb"
install -m 0755 "$repo/initramfs/hid-keyboard" "$staging/usr/bin/hid-keyboard"
install -m 0755 "$repo/initramfs/hid-absolute-mouse" "$staging/usr/bin/hid-absolute-mouse"
mkdir -p "$staging/usr/share"
python3 - "$repo/initramfs/hid-absolute-mouse.report.hex" "$staging/usr/share/hid-absolute-mouse.report" <<'PY'
import sys
from pathlib import Path
Path(sys.argv[2]).write_bytes(bytes.fromhex(Path(sys.argv[1]).read_text()))
PY
install -m 0755 "$repo/initramfs/hid-relative-mouse" "$staging/usr/bin/hid-relative-mouse"
mkdir -p "$staging/usr/share"
python3 - "$repo/initramfs/hid-relative-mouse.report.hex" "$staging/usr/share/hid-relative-mouse.report" <<'PY'
import sys
from pathlib import Path
Path(sys.argv[2]).write_bytes(bytes.fromhex(Path(sys.argv[1]).read_text()))
PY
"${CROSS_COMPILE}gcc" -std=c11 -Os -static -s \
    -Wall -Wextra -Werror \
    -o "$staging/usr/bin/v4l2-test" "$repo/initramfs/v4l2-test.c"
if ! file "$staging/usr/bin/v4l2-test" \
    | grep -Eq 'ARM aarch64.*statically linked'; then
    echo "v4l2-test is not a static AArch64 executable" >&2
    exit 1
fi
for utility in ip ping lsusb v4l2-test; do
    if ! test -e "$staging/sbin/$utility" && ! test -L "$staging/sbin/$utility" \
       && ! test -e "$staging/bin/$utility" && ! test -L "$staging/bin/$utility" \
       && ! test -e "$staging/usr/bin/$utility" \
       && ! test -L "$staging/usr/bin/$utility"; then
        echo "required initramfs utility is missing: $utility" >&2
        exit 1
    fi
done
find "$staging" -exec touch -h -d '@0' {} +
(
    cd "$staging"
    find . -print0 \
        | LC_ALL=C sort -z \
        | cpio --null --create --format=newc --owner=0:0 --reproducible 2>/dev/null \
        | gzip -n -9 > "$artifacts/initramfs.cpio.gz.tmp"
)
mv "$artifacts/initramfs.cpio.gz.tmp" "$artifacts/initramfs.cpio.gz"
chmod 0644 "$artifacts/initramfs.cpio.gz"

file "$artifacts/Image"
gzip -t "$artifacts/initramfs.cpio.gz"
