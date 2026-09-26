#!/bin/bash
set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)/build/release/verify.sh"
repo=$(cd "$(dirname "$0")/../.." && pwd)
cd "$repo"
source build/ubuntu/versions.env
source build/ustreamer/versions.env
source build/kvmd/versions.env
mode=${1:-package}
case "$mode" in package|rootfs) ;; *) exit 2;; esac
mkdir -p out/kvmd/downloads
archive=out/kvmd/downloads/kvmd.tar.gz
if ! test -f "$archive"; then
    curl -fL --retry 3 "$KVMD_URL" -o "$archive.part"
    mv "$archive.part" "$archive"
fi
release_verify_file "$KVMD_SHA256" "$archive"
release_verify_file "$M75_ROOTFS_SHA256" out/ustreamer/artifacts/rootfs.tar.gz
release_verify_list build/ubuntu/m5-artifacts.sha256
release_verify_list build/ustreamer/m7-artifacts.sha256
release_verify_file "$KVMD_PATCH_SHA256" build/kvmd/video-only.patch
sudo -n docker image inspect "$BUILDER_IMAGE" > out/kvmd/builder-image.json
actual_builder=$(python3 -c 'import json; print(json.load(open("out/kvmd/builder-image.json"))[0]["Id"])')
release_verify_builder "$actual_builder" "$USTREAMER_BUILDER_ID"
if [ "$mode" = rootfs ]; then
    release_verify_list build/kvmd/package.sha256
fi
sudo -n docker run --rm --privileged -e "SOURCE_DATE_EPOCH=$SOURCE_DATE_EPOCH" -e "BLIKVM_RELEASE_BUILD=${BLIKVM_RELEASE_BUILD:-0}" \
  -v "$repo:/work" "$BUILDER_IMAGE" \
  bash -c 'cp /work/build/kvmd/in-container.sh /tmp/ustreamer-build.sh; exec unshare --user --map-users=0,0,65536 --map-groups=0,0,65536 --mount --pid --fork --mount-proc /tmp/ustreamer-build.sh "$1"' -- "$mode"
sudo -n chown -R "$(id -u):$(id -g)" out/kvmd/artifacts
