#!/bin/bash
set -euo pipefail
umask 022
source /work/build/ubuntu/versions.env
# Refuse direct execution in the host's initial user namespace.
read -r uid_inner uid_outer uid_count < /proc/self/uid_map
[ "$uid_inner:$uid_outer:$uid_count" = 0:0:65536 ] || {
    echo 'Builder requires its isolated 65536-ID user namespace' >&2; exit 2;
}
source /work/build/ustreamer/versions.env
root=/work/out/ustreamer/$1-rootfs
output=/work/out/ustreamer/artifacts
registration=/proc/sys/fs/binfmt_misc/blikvm-m7-aarch64
mounted=()
registered=0
cleanup() {
    # Shell builtin first: recovery must not depend on spawning a native binary.
    if [ "$registered" = 1 ]; then echo -1 > "$registration"; fi
    registered=0
    for ((i=${#mounted[@]}-1; i>=0; i--)); do
        # Imported submounts are locked in a user namespace; detach each whole
        # container-private tree, never try to unmount its inherited children.
        umount -l "${mounted[i]}"
    done
}
trap cleanup EXIT
if ! mountpoint -q /proc/sys/fs/binfmt_misc; then
    mount -t binfmt_misc binfmt_misc /proc/sys/fs/binfmt_misc
    mounted+=(/proc/sys/fs/binfmt_misc)
fi
test ! -e "$registration"
# binfmt_misc expects textual \\xNN escapes, NOT literal NUL bytes.
rule=$(python3 /work/build/ubuntu/binfmt-rule.py /usr/bin/qemu-aarch64-static)
registered=1
printf '%s\n' "$rule" > /proc/sys/fs/binfmt_misc/register
cat "$registration"
test ! -e "$root"
mkdir -p "$root" "$output"
printf '%s  %s\n' "$M7_ROOTFS_SHA256" /work/out/ubuntu/artifacts/rootfs.tar.gz | sha256sum -c -
tar --numeric-owner -xpf /work/out/ubuntu/artifacts/rootfs.tar.gz -C "$root"
for directory in proc sys dev dev/pts run; do mkdir -p "$root/$directory"; done
mount -t proc proc "$root/proc"; mounted+=("$root/proc")
mount --rbind /dev "$root/dev"; mount --make-rslave "$root/dev"
mounted+=("$root/dev")
# Package installation needs no live hardware sysfs; leave /sys empty.
mount -t tmpfs tmpfs "$root/run"; mounted+=("$root/run")
chroot "$root" /bin/true
cp /etc/resolv.conf "$root/etc/resolv.conf"
printf '#!/bin/sh\nexit 101\n' > "$root/usr/sbin/policy-rc.d"
chmod 755 "$root/usr/sbin/policy-rc.d"
chroot "$root" apt-get update
if [ "$1" = package ]; then
    chroot "$root" apt-get install -y --no-install-recommends build-essential pkg-config libjpeg-dev libevent-dev libbsd-dev
    chroot "$root" dpkg-query -W '-f=${Package}\t${Version}\t${Architecture}\n' > "$output/build-packages.tsv"
    printf '%s  %s\n' "$USTREAMER_SHA256" /work/out/ustreamer/downloads/ustreamer.tar.gz | sha256sum -c -
    mkdir -p "$root/build/source" "$root/build/pkg/DEBIAN"
    tar -xf /work/out/ustreamer/downloads/ustreamer.tar.gz --strip-components=1 -C "$root/build/source"
    printf '%s  %s\n' "$USTREAMER_PATCH_SHA256" /work/build/ustreamer/capture-controls.patch | sha256sum -c -
    cp /work/build/ustreamer/capture-controls.patch "$root/build/capture-controls.patch"
    chroot "$root" /bin/bash -c 'cd /build/source; patch -p1 < /build/capture-controls.patch'
    chroot "$root" /bin/bash -c 'cd /build/source; make -j3 WITH_GPIO=0 WITH_SYSTEMD=0 WITH_PYTHON=0 WITH_JANUS=0 WITH_V4P=0 CFLAGS="-O2 -g0 -ffile-prefix-map=/build/source=. -fstack-protector-strong -D_FORTIFY_SOURCE=2" LDFLAGS="-Wl,-z,relro,-z,now"'
    install -Dm755 "$root/build/source/ustreamer" "$root/build/pkg/usr/bin/ustreamer"
    chroot "$root" strip /build/pkg/usr/bin/ustreamer
    install -Dm644 "$root/build/source/LICENSE" "$root/build/pkg/usr/share/doc/ustreamer/copyright"
    install -Dm644 /work/build/ustreamer/ustreamer.service "$root/build/pkg/usr/lib/systemd/system/ustreamer.service"
    install -Dm644 /work/build/ustreamer/99-blikvm-video.rules "$root/build/pkg/usr/lib/udev/rules.d/99-blikvm-video.rules"
    mkdir -p "$root/build/pkg/usr/lib/sysusers.d"
    echo 'u ustreamer - "BliKVM video service" /nonexistent /usr/sbin/nologin' > "$root/build/pkg/usr/lib/sysusers.d/ustreamer.conf"
    cat > "$root/build/pkg/DEBIAN/control" <<CONTROL
Package: ustreamer
Version: $PACKAGE_VERSION
Architecture: arm64
Maintainer: BliKVM Port <noreply@localhost>
Depends: libc6, libjpeg8, libevent-2.1-7t64, libevent-pthreads-2.1-7t64, libbsd0, libatomic1, systemd, udev
Description: Pinned native MJPEG streamer for the qualified BliKVM MS2131
CONTROL
    cat > "$root/build/pkg/DEBIAN/postinst" <<'POST'
#!/bin/sh
set -e
if [ "$1" = configure ]; then
    systemd-sysusers /usr/lib/sysusers.d/ustreamer.conf
    systemctl enable ustreamer.service
    if [ -d /run/systemd/system ]; then
        systemctl daemon-reload
        udevadm control --reload
        udevadm trigger --subsystem-match=video4linux
    fi
fi
POST
    cat > "$root/build/pkg/DEBIAN/prerm" <<'PRE'
#!/bin/sh
set -e
if [ -d /run/systemd/system ]; then
    systemctl stop ustreamer.service
fi
PRE
    cat > "$root/build/pkg/DEBIAN/postrm" <<'POSTREMOVE'
#!/bin/sh
set -e
if [ "$1" = remove ] || [ "$1" = purge ]; then
    systemctl disable ustreamer.service || true
fi
if [ -d /run/systemd/system ]; then
    systemctl daemon-reload
    udevadm control --reload
fi
POSTREMOVE
    chmod 755 "$root/build/pkg/DEBIAN/"{postinst,prerm,postrm}
    find "$root/build/pkg" -exec touch -h -d "@$SOURCE_DATE_EPOCH" {} +
    dpkg-deb --root-owner-group -Zgzip -z9 --build "$root/build/pkg" "$root/build/ustreamer.deb"
    cp "$root/build/ustreamer.deb" "$output/ustreamer_${PACKAGE_VERSION}_arm64.deb"
    cp "$root/build/pkg/usr/bin/ustreamer" "$output/ustreamer"
    chroot "$root" /build/pkg/usr/bin/ustreamer --version > "$output/version.txt"
    chroot "$root" /build/pkg/usr/bin/ustreamer --device-fps=30 --quality=0 --help > "$output/help.txt"
    if chroot "$root" /build/pkg/usr/bin/ustreamer --device-fps=-1 > "$output/invalid-device-fps.txt" 2>&1; then exit 1; fi
    if chroot "$root" /build/pkg/usr/bin/ustreamer --quality=101 > "$output/invalid-quality.txt" 2>&1; then exit 1; fi
    chroot "$root" ldd /build/pkg/usr/bin/ustreamer > "$output/binary-libraries.txt"
else
    printf '%s  %s\n' "$USTREAMER_PACKAGE_SHA256" "$output/ustreamer_${PACKAGE_VERSION}_arm64.deb" | sha256sum -c -
    cp "$output/ustreamer_${PACKAGE_VERSION}_arm64.deb" "$root/tmp/ustreamer.deb"
    chroot "$root" apt-get install -y --no-install-recommends /tmp/ustreamer.deb
    sed -i '1i enable ustreamer.service' "$root/etc/systemd/system-preset/00-blikvm-lab.preset"
    chroot "$root" dpkg-query -W '-f=${Package}\t${Version}\t${Architecture}\n' > "$output/packages.tsv"
    cp "$output/packages.tsv" "$root/etc/blikvm-packages.tsv"
    printf 'ustreamer=%s\nustreamer_commit=%s\n' "$PACKAGE_VERSION" "$USTREAMER_COMMIT" >> "$root/etc/blikvm-build"
    echo '# Isolated lab: no DNS server or default route.' > "$root/etc/resolv.conf"
    rm -f "$root/usr/sbin/policy-rc.d" "$root/var/cache/ldconfig/aux-cache"
    chroot "$root" apt-get clean
    find "$root/var/log" -type f -exec truncate -s 0 {} +
    rm -rf "$root/var/lib/apt/lists/"* "$root/tmp/"* "$root/var/tmp/"*
    python3 - "$root" "$SOURCE_DATE_EPOCH" <<'PY'
import sys
from pathlib import Path
for name in ('shadow', 'shadow-'):
    p = Path(sys.argv[1]) / 'etc' / name
    if p.exists():
        rows = [s.split(':') for s in p.read_text().splitlines()]
        for row in rows: row[2] = str(int(sys.argv[2]) // 86400)
        p.write_text(''.join(':'.join(row)+'\n' for row in rows))
PY
    cleanup
    mounted=(); registered=0
    find "$root" -xdev -exec touch -h -d "@$SOURCE_DATE_EPOCH" {} +
    tar --sort=name --mtime="@$SOURCE_DATE_EPOCH" --numeric-owner --format=gnu -C "$root" -cf - . | gzip -n -9 > "$output/rootfs.tar.gz"
    (cd "$root"; find . -xdev -print0 | LC_ALL=C sort -z | cpio --null -o -H newc --reproducible 2>/dev/null | gzip -n -9) > "$output/initramfs.cpio.gz"
    cp /work/out/ubuntu/artifacts/{Image,sun50i-h616-blikvm-v4.dtb,linux.config} "$output/"
fi
cd "$output"
find . -maxdepth 1 -type f ! -name SHA256SUMS ! -name manifest.json -printf '%f\n' | LC_ALL=C sort | xargs sha256sum > /tmp/ustreamer-SHA256SUMS
cp /tmp/ustreamer-SHA256SUMS SHA256SUMS
