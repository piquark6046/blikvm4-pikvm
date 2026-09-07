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
source /work/build/kvmd/versions.env
source /work/build/kvmd-web/versions.env
root=/work/out/kvmd-lan/rootfs
output=/work/out/kvmd-lan/artifacts
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
printf '%s  %s\n' "3a40cafa3e690a0317a176d6bd9e5f2f2b96ce771514518d2cde69cdd2836347" /work/out/kvmd-web/artifacts/rootfs.tar.gz | sha256sum -c -
tar --numeric-owner -xpf /work/out/kvmd-web/artifacts/rootfs.tar.gz -C "$root"
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
chroot "$root" apt-get install -y --no-install-recommends nftables
install -m 644 /work/build/kvmd-lan/access.nft "$root/etc/kvmd/access.nft"
install -m 644 /work/build/kvmd-lan/nginx.conf "$root/etc/kvmd/nginx/nginx.conf"
install -m 644 /work/build/kvmd-lan/blikvm-access.service "$root/etc/systemd/system/blikvm-access.service"
mkdir -p "$root/etc/systemd/system/nginx.service.d"
install -m 644 /work/build/kvmd-lan/nginx-access.conf "$root/etc/systemd/system/nginx.service.d/access.conf"
chroot "$root" systemctl disable nftables.service
chroot "$root" systemctl enable blikvm-access.service
sed -i '1i enable blikvm-access.service\ndisable nftables.service' "$root/etc/systemd/system-preset/00-blikvm-lab.preset"
chroot "$root" dpkg-query -W '-f=${Package}\t${Version}\t${Architecture}\n' > "$output/packages.tsv"
if test -e /work/build/kvmd-lan/packages.lock.tsv; then
    cmp /work/build/kvmd-lan/packages.lock.tsv "$output/packages.tsv"
fi
cp "$output/packages.tsv" "$root/etc/blikvm-packages.tsv"
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
    cp /work/out/kvmd-lan/kernel/{Image,sun50i-h616-blikvm-v4.dtb,linux.config} "$output/"
cd "$output"
find . -maxdepth 1 -type f ! -name SHA256SUMS ! -name manifest.json -printf '%f\n' | LC_ALL=C sort | xargs sha256sum > /tmp/ustreamer-SHA256SUMS
cp /tmp/ustreamer-SHA256SUMS SHA256SUMS
