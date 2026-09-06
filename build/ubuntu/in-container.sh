#!/bin/bash
set -euo pipefail
umask 022
source /work/build/ubuntu/versions.env
# Refuse direct execution in the host's initial user namespace.
read -r uid_inner uid_outer uid_count < /proc/self/uid_map
[ "$uid_inner:$uid_outer:$uid_count" = 0:0:65536 ] || {
    echo 'Builder requires its isolated 65536-ID user namespace' >&2; exit 2;
}
root=/work/out/ubuntu/rootfs
output=/work/out/ubuntu/artifacts
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
if [ "$1" = packages ]; then
    test ! -e "$root" # Fresh build only; retain failures for inspection.
    rm -f /work/out/ubuntu/packages.complete
    mkdir -p "$root"
    gpgv --keyring /work/out/ubuntu/downloads/ubuntu-archive-keyring.gpg \
      /work/out/ubuntu/downloads/SHA256SUMS.gpg /work/out/ubuntu/downloads/SHA256SUMS
    printf '%s  %s\n' "$UBUNTU_SHA256" "/work/out/ubuntu/downloads/$UBUNTU_ARCHIVE" | sha256sum -c -
    tar --numeric-owner -xpf "/work/out/ubuntu/downloads/$UBUNTU_ARCHIVE" -C "$root"
fi
for directory in proc sys dev dev/pts run; do mkdir -p "$root/$directory"; done
mount -t proc proc "$root/proc"; mounted+=("$root/proc")
mount --rbind /dev "$root/dev"; mount --make-rslave "$root/dev"
mounted+=("$root/dev")
# Package installation needs no live hardware sysfs; leave /sys empty.
mount -t tmpfs tmpfs "$root/run"; mounted+=("$root/run")
chroot "$root" /bin/true
if [ "$1" = packages ]; then
    rm -f "$root/etc/resolv.conf"
    cp /etc/resolv.conf "$root/etc/resolv.conf"
    mkdir -p "$root/usr/sbin" "$root/etc/apt/apt.conf.d"
    printf '#!/bin/sh\nexit 101\n' > "$root/usr/sbin/policy-rc.d"
    chmod 755 "$root/usr/sbin/policy-rc.d"
    rm -f "$root/etc/apt/sources.list" "$root/etc/apt/sources.list.d/ubuntu.sources"
    cat > "$root/etc/apt/sources.list.d/ubuntu.sources" <<EOF
Types: deb
URIs: https://snapshot.ubuntu.com/ubuntu/$APT_SNAPSHOT/
Suites: resolute resolute-updates resolute-security
Components: main universe
Architectures: arm64
Signed-By: /usr/share/keyrings/ubuntu-archive-keyring.gpg
Check-Valid-Until: no
EOF
    # The signed base has no CA bundle; copy the builder's public trust store
    # only to bootstrap HTTPS apt, then the signed ca-certificates package owns it.
    mkdir -p "$root/etc/ssl/certs"
    cp /etc/ssl/certs/ca-certificates.crt "$root/etc/ssl/certs/"
    printf 'Acquire::https::CaInfo "/etc/ssl/certs/ca-certificates.crt";\nAPT::Update::Error-Mode "any";\n' > "$root/etc/apt/apt.conf.d/81-blikvm-trust"
    printf 'APT::Install-Recommends "false";\nAPT::Install-Suggests "false";\n' > "$root/etc/apt/apt.conf.d/80blikvm-minimal"
    chroot "$root" apt-get update
    # Ubuntu's libgpiod command-line package is named gpiod.
    chroot "$root" apt-get install -y --no-install-recommends \
      systemd-sysv systemd-resolved udev kmod iproute2 ethtool openssh-server \
      ca-certificates sudo rsync curl usbutils v4l-utils gpiod \
      iputils-ping procps util-linux less nano file strace busybox-static \
      dbus libnss-systemd libnss-myhostname tzdata
    chroot "$root" dpkg-query -W '-f=${Package}\t${Version}\t${Architecture}\n' > /work/out/ubuntu/packages.tsv
    cp "$root/var/lib/dpkg/status" /work/out/ubuntu/dpkg-status
    touch /work/out/ubuntu/packages.complete
    exit 0
fi
test -f /work/out/ubuntu/packages.complete
test -s /provision/authorized_keys
mkdir -p "$output"
install -m 644 /provision/authorized_keys /tmp/m7-public-key
chroot "$root" id blikvm >/dev/null 2>&1 || chroot "$root" useradd -m -s /bin/bash -G sudo blikvm
chroot "$root" passwd -l root
chroot "$root" passwd -l blikvm
install -d -m 700 -o 1000 -g 1000 "$root/home/blikvm/.ssh"
install -m 600 -o 1000 -g 1000 /tmp/m7-public-key "$root/home/blikvm/.ssh/authorized_keys"
echo 'blikvm ALL=(ALL:ALL) NOPASSWD: ALL' > "$root/etc/sudoers.d/90-blikvm-lab"
chmod 440 "$root/etc/sudoers.d/90-blikvm-lab"
echo blikvm-m7 > "$root/etc/hostname"
echo LANG=C.UTF-8 > "$root/etc/locale.conf"
echo KEYMAP=us > "$root/etc/vconsole.conf"
echo Etc/UTC > "$root/etc/timezone"
printf '127.0.0.1 localhost\n127.0.1.1 blikvm-m7\n' > "$root/etc/hosts"
echo uninitialized > "$root/etc/machine-id"
rm -f "$root/var/lib/dbus/machine-id"
ln -s /etc/machine-id "$root/var/lib/dbus/machine-id"
rm -f "$root/etc/resolv.conf"
echo '# Isolated M7 lab: no DNS server and no default gateway.' > "$root/etc/resolv.conf"
mkdir -p "$root/etc/systemd/network" "$root/etc/ssh/sshd_config.d"
mkdir -p "$root/etc/systemd/system-preset"
cat > "$root/etc/systemd/system-preset/00-blikvm-lab.preset" <<'EOF'
# First boot reapplies presets when machine-id is uninitialized.
enable systemd-networkd.service
enable systemd-networkd-wait-online.service
enable serial-getty@ttyS0.service
enable ssh.service
enable sshd-keygen.service
disable ssh.socket
disable systemd-resolved.service
disable systemd-resolved*.socket
disable apt-daily*.timer
disable motd-news.timer
disable fstrim.timer
disable e2scrub*.timer
disable e2scrub_reap.service
EOF
cat > "$root/etc/systemd/network/10-lab.network" <<'EOF'
[Match]
Name=eth0
[Network]
Address=192.168.88.2/24
DHCP=no
LinkLocalAddressing=no
IPv6AcceptRA=no
LLMNR=no
MulticastDNS=no
[Link]
RequiredForOnline=routable
EOF
cat > "$root/etc/ssh/sshd_config.d/00-blikvm-lab.conf" <<'EOF'
ListenAddress 192.168.88.2
PasswordAuthentication no
KbdInteractiveAuthentication no
PermitRootLogin no
PubkeyAuthentication yes
AuthenticationMethods publickey
AllowUsers blikvm
UseDNS no
EOF
mkdir -p "$root/etc/systemd/system/serial-getty@ttyS0.service.d"
cat > "$root/etc/systemd/system/serial-getty@ttyS0.service.d/lab.conf" <<'EOF'
# Temporary isolated-lab console access, without a baked-in password.
[Service]
ExecStart=
ExecStart=-/sbin/agetty --autologin blikvm --keep-baud 115200,57600,38400,9600 - $TERM
EOF
mkdir -p "$root/etc/systemd/system/ssh.service.d"
printf '[Unit]\nRequires=sshd-keygen.service\nAfter=sshd-keygen.service network-online.target\nWants=network-online.target\n' > "$root/etc/systemd/system/ssh.service.d/ram-root.conf"
chroot "$root" systemctl disable ssh.socket systemd-resolved.service || true
chroot "$root" systemctl enable systemd-networkd.service systemd-networkd-wait-online.service ssh.service sshd-keygen.service serial-getty@ttyS0.service
chroot "$root" systemctl set-default multi-user.target
rm -f "$root/etc/ssh/ssh_host_"* "$root/var/lib/systemd/random-seed" "$root/usr/sbin/policy-rc.d"
# Reuse the frozen M5 executable and descriptors; do not redesign the gadget.
for helper in hid-keyboard hid-absolute-mouse hid-relative-mouse gadget-storage; do
    install -m 755 "/work/initramfs/$helper" "$root/usr/bin/$helper"
done
python3 - "$root" <<'PY'
import sys
from pathlib import Path
r = Path(sys.argv[1])
for name in ('hid-absolute-mouse', 'hid-relative-mouse'):
    (r / 'usr/share' / (name + '.report')).write_bytes(bytes.fromhex(Path('/work/initramfs/' + name + '.report.hex').read_text()))
PY
python3 /work/build/make-storage-image.py "$root/usr/share"
mkdir -p /tmp/frozen-m5
(cd /tmp/frozen-m5; gzip -dc /work/out/build/artifacts/initramfs.cpio.gz | cpio -id --quiet usr/bin/v4l2-test)
install -m 755 /tmp/frozen-m5/usr/bin/v4l2-test "$root/usr/bin/v4l2-test"
# All M5 drivers are built in (CONFIG_MODULES=n): no invented modules tree.
cp /work/out/ubuntu/packages.tsv "$root/etc/blikvm-packages.tsv"
printf 'milestone=M7\nubuntu_base=%s\napt_snapshot=%s\nsource_date_epoch=%s\nroot_transport=ram-rw\n' "$UBUNTU_VERSION" "$APT_SNAPSHOT" "$SOURCE_DATE_EPOCH" > "$root/etc/blikvm-build"
printf 'builder_sha256=%s\nkernel_sha256=%s\n' \
  "$(sha256sum /work/build/ubuntu/in-container.sh | cut -d' ' -f1)" \
  "$(sha256sum /work/out/ubuntu/kernel/Image | cut -d' ' -f1)" >> "$root/etc/blikvm-build"
python3 - "$root" "$SOURCE_DATE_EPOCH" <<'PY'
from pathlib import Path
import sys
for name in ('shadow', 'shadow-'):
    path = Path(sys.argv[1]) / 'etc' / name
    if path.exists():
        rows = [line.split(':') for line in path.read_text().splitlines()]
        for row in rows:
            row[2] = str(int(sys.argv[2]) // 86400)
        path.write_text(''.join(':'.join(row) + '\n' for row in rows))
PY
rm -f "$root/var/cache/ldconfig/aux-cache"
chroot "$root" apt-get clean
find "$root/var/log" -type f -exec truncate -s 0 {} +
rm -rf "$root/var/lib/apt/lists/"* "$root/tmp/"* "$root/var/tmp/"*
cleanup
mounted=(); registered=0
find "$root" -xdev -exec touch -h -d "@$SOURCE_DATE_EPOCH" {} +
tar --sort=name --mtime="@$SOURCE_DATE_EPOCH" --numeric-owner --format=gnu -C "$root" -cf - . | gzip -n -9 > "$output/rootfs.tar.gz"
(cd "$root"; find . -xdev -print0 | LC_ALL=C sort -z | cpio --null -o -H newc --reproducible 2>/dev/null | gzip -n -9) > "$output/initramfs.cpio.gz"
cp /work/out/ubuntu/kernel/{Image,sun50i-h616-blikvm-v4.dtb,linux.config} "$output/"
cp /work/out/ubuntu/packages.tsv "$output/"
cd "$output"
sha256sum Image sun50i-h616-blikvm-v4.dtb linux.config rootfs.tar.gz initramfs.cpio.gz packages.tsv > SHA256SUMS
