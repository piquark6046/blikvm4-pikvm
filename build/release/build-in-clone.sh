#!/bin/bash
set -euo pipefail
repo=$(cd "$(dirname "$0")/../.." && pwd)
cd "$repo"
test ! -e out || { echo 'clean release source requires no out/' >&2; exit 2; }
test -z "$(git status --porcelain)" || { echo 'release source must be clean' >&2; exit 2; }
export BLIKVM_RELEASE_BUILD=1 JOBS=2
mkdir -p out/release
disk_samples=out/release/disk-samples.tsv
disk_monitor() {
    while :; do
        df -B1 --output=size,used,avail / | tail -n 1 >> "$disk_samples"
        sleep 5
    done
}
disk_monitor & monitor_pid=$!
report_disk() {
    kill "$monitor_pid" 2>/dev/null || true
    wait "$monitor_pid" 2>/dev/null || true
    awk 'NR == 1 || $2 > peak {peak=$2} NR == 1 || $3 < free {free=$3}
         END {printf "release disk peak_used_bytes=%s minimum_free_bytes=%s samples=%d\n", peak, free, NR}' \
        "$disk_samples"
}
trap report_disk EXIT
source build/ubuntu/versions.env
source build/versions.env
lock() { python3 build/release/lock.py record "$@"; }
usage() { df -h /; du -xhd1 out 2>/dev/null || true; sudo -n du -xhd1 /var/lib/docker 2>/dev/null || true; }
cleanup_tree() {
    local name=$1 path="$repo/out/$1"
    case "$name" in
        ubuntu/rootfs|ustreamer/package-rootfs|ustreamer/rootfs-rootfs|\
        kvmd/package-rootfs|kvmd/rootfs-rootfs|\
        kvmd-web/package-rootfs|kvmd-web/rootfs-rootfs|\
        kvmd-lan/rootfs|kvmd-hid/package-rootfs|kvmd-hid/rootfs-rootfs|\
        kvmd-msd/package-rootfs|kvmd-msd/rootfs-rootfs|\
        src/linux-7.2.3|build/linux-7.2.3) ;;
        *) echo "unapproved cleanup path: $name" >&2; exit 2;;
    esac
    test ! -L "$path"
    if test -d "$path"; then sudo -n rm -rf -- "$path"; fi
}
ci_drop_image() {
    if [[ ${GITHUB_ACTIONS:-false} == true ]]; then
        sudo -n docker image rm "$1"
    fi
}
usage

# M5 baseline artifacts and kernel source, kept in this disposable clone.
build/build.sh
lock out/build/artifacts/{Image,initramfs.cpio.gz,linux.config,manifest.json,sun50i-h616-blikvm-v4.dtb}
patch --fuzz=0 -d out/src/linux-7.2.3 -p1 < build/linux-candidates/ms2131-bulk-eof-reject.patch
build/ubuntu/build-kernel.sh
build/ubuntu/build.sh packages
build/ubuntu/build.sh finalize --public
lock out/ubuntu/artifacts/{Image,initramfs.cpio.gz,linux.config,rootfs.tar.gz,sun50i-h616-blikvm-v4.dtb}
cleanup_tree ubuntu/rootfs
usage

build/ustreamer/build.sh package
lock out/ustreamer/artifacts/ustreamer_6.65-1blikvm2_arm64.deb
cleanup_tree ustreamer/package-rootfs
build/ustreamer/build.sh rootfs
lock out/ustreamer/artifacts/{Image,linux.config,rootfs.tar.gz,sun50i-h616-blikvm-v4.dtb}
cleanup_tree ustreamer/rootfs-rootfs
build/kvmd/build.sh package
lock out/kvmd/artifacts/kvmd-video_4.213-1blikvm1_arm64.deb
cleanup_tree kvmd/package-rootfs
build/kvmd/build.sh rootfs
lock out/kvmd/artifacts/rootfs.tar.gz
cleanup_tree kvmd/rootfs-rootfs
build/kvmd-web/build.sh package
lock out/kvmd-web/artifacts/kvmd-web_4.213-1blikvm2_arm64.deb
cleanup_tree kvmd-web/package-rootfs
build/kvmd-web/build.sh rootfs
lock out/kvmd-web/artifacts/{linux.config,rootfs.tar.gz}
cleanup_tree kvmd-web/rootfs-rootfs
bash build/kvmd-lan/build-kernel.sh
bash build/kvmd-lan/build.sh
lock out/kvmd-lan/artifacts/{Image,linux.config,rootfs.tar.gz,sun50i-h616-blikvm-v4.dtb}
cleanup_tree kvmd-lan/rootfs
cleanup_tree src/linux-7.2.3
cleanup_tree build/linux-7.2.3
ci_drop_image blikvm-release-linux:20260904
bash build/kvmd-hid/build.sh package
lock out/kvmd-hid/artifacts/kvmd-web_4.213-1blikvm3_arm64.deb
cleanup_tree kvmd-hid/package-rootfs
bash build/kvmd-hid/build.sh rootfs
lock out/kvmd-hid/artifacts/rootfs.tar.gz
cleanup_tree kvmd-hid/rootfs-rootfs
bash build/kvmd-msd/build.sh package
lock out/kvmd-msd/artifacts/kvmd-web_4.213-1blikvm4_arm64.deb
cleanup_tree kvmd-msd/package-rootfs
bash build/kvmd-msd/build.sh rootfs
lock out/kvmd-msd/artifacts/rootfs.tar.gz
cleanup_tree kvmd-msd/rootfs-rootfs
usage

python3 build/logging/build.py --release --output out/release/logging
sudo -n docker run --rm -v "$repo/out/release/logging:/candidate" \
    -v "$repo/build/logging/cpio.sh:/build-cpio.sh:ro" "$BUILDER_IMAGE" bash /build-cpio.sh
lock out/release/logging/{rootfs.tar.gz,initramfs.cpio.gz}
python3 build/release/make-input-lock.py --output out/release/image-inputs.lock.json
if [[ ${GITHUB_ACTIONS:-false} == true ]]; then
    # All later inputs are named in image-inputs.lock.json. Keep those bytes.
    for directory in out/build/artifacts out/ubuntu/artifacts out/kvmd/artifacts \
                     out/kvmd-web/artifacts out/kvmd-hid/artifacts; do
        test ! -L "$directory"
        sudo -n rm -rf -- "$directory"
    done
    sudo -n rm -f -- out/ustreamer/artifacts/rootfs.tar.gz \
        out/kvmd-lan/artifacts/rootfs.tar.gz out/kvmd-msd/artifacts/rootfs.tar.gz
fi
build/release/bootloader.sh
if [[ ${GITHUB_ACTIONS:-false} == true ]]; then
    sudo -n rm -rf -- out/release/bootloader/u-boot out/release/bootloader/tf-a
fi
ci_drop_image blikvm-release-bootloader:20260904
sudo -n docker build -f build/release/AssemblyContainerfile -t blikvm-release-assembly:20260904 build/release
sudo -n docker run --rm --privileged -e BLIKVM_RELEASE_BUILD=1 \
    -v "$repo:/work" -w /work blikvm-release-assembly:20260904 \
    python3 build/image/assemble.py --revision p2-r1-candidate1 \
    --input-lock out/release/image-inputs.lock.json \
    --bootloader-layout out/release/bootloader/layout.json \
    --vendor-dir out/release/bootloader --output out/release/assembly
sudo -n chown -R "$(id -u):$(id -g)" out/release/assembly out/release/logging
ci_drop_image "$BUILDER_IMAGE"
ci_drop_image blikvm-release-assembly:20260904
usage
python3 build/release/candidate.py out/release/assembly out/release/candidate
