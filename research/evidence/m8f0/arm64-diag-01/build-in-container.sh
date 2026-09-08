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
root=/work/out/m8f0/arm64-diag-01/build-root
output=/work/out/m8f0/arm64-diag-01/artifacts
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
chroot "$root" apt-get install -y --no-install-recommends build-essential pkg-config libjpeg-dev libevent-dev libbsd-dev libssl-dev
chroot "$root" dpkg-query -W '-f=${Package}\t${Version}\t${Architecture}\n' > "$output/build-packages.tsv"
cp -a "$root/etc/apt" "$output/apt-configuration"
mkdir "$output/dependency-archives"
cp "$root"/var/cache/apt/archives/*.deb "$output/dependency-archives/"
sha256sum "$output"/dependency-archives/*.deb > "$output/dependency-archives.sha256"
cp -a /work/out/m8f0/arm64-diag-01/source "$root/build-source"
chroot "$root" gcc --version > "$output/compiler.txt"
chroot "$root" /bin/bash -c 'cd /build-source; make -j3 WITH_GPIO=0 WITH_SYSTEMD=0 WITH_PYTHON=0 WITH_JANUS=0 WITH_V4P=0 CFLAGS="-O2 -g0 -ffile-prefix-map=/build-source=. -fstack-protector-strong -D_FORTIFY_SOURCE=2" LDFLAGS="-Wl,-z,relro,-z,now"'
mkdir -p "$output/pkg/DEBIAN" "$output/pkg/usr/bin" "$output/pkg/usr/share/doc/ustreamer"
install -m755 "$root/build-source/src/ustreamer.bin" "$output/pkg/usr/bin/ustreamer"
cp "$root/build-source/src/ustreamer.bin" "$output/ustreamer-unstripped"
chroot "$root" strip /build-source/src/ustreamer.bin
install -m755 "$root/build-source/src/ustreamer.bin" "$output/pkg/usr/bin/ustreamer"
cp "$root/build-source/LICENSE" "$output/pkg/usr/share/doc/ustreamer/copyright"
cat > "$output/pkg/DEBIAN/control" <<'CONTROL'
Package: ustreamer
Version: 6.65-1blikvm2+taildiag1
Architecture: arm64
Maintainer: BliKVM Port <noreply@localhost>
Depends: libc6, libjpeg8, libevent-2.1-7t64, libevent-pthreads-2.1-7t64, libbsd0, libatomic1, libssl3t64
Description: M8-F0 diagnostic-only JPEG boundary instrumentation, never qualified
CONTROL
find "$output/pkg" -exec touch -h -d "@$SOURCE_DATE_EPOCH" {} +
dpkg-deb --root-owner-group -Zgzip -z9 --build "$output/pkg" "$output/ustreamer_6.65-1blikvm2+taildiag1_arm64.deb"
cp "$output/pkg/usr/bin/ustreamer" "$output/ustreamer"
chroot "$root" /build-source/ustreamer --version > "$output/version.txt"
chroot "$root" ldd /build-source/ustreamer > "$output/binary-libraries.txt"
sha256sum "$output/ustreamer" "$output/ustreamer_6.65-1blikvm2+taildiag1_arm64.deb" > "$output/SHA256SUMS"
