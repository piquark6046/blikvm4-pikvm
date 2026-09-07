#!/bin/bash
set -euo pipefail
repo=$(cd "$(dirname "$0")/../.." && pwd)
cd "$repo"
source build/ubuntu/versions.env
source build/ustreamer/versions.env
source build/kvmd/versions.env
source build/kvmd-web/versions.env
mode=${1:-package}
case "$mode" in package|rootfs) ;; *) exit 2;; esac
mkdir -p out/kvmd-web/downloads
archive=out/kvmd-web/downloads/kvmd.tar.gz
if ! test -f "$archive"; then
    curl -fL --retry 3 "$KVMD_URL" -o "$archive.part"
    mv "$archive.part" "$archive"
fi
printf '%s  %s\n' "$KVMD_SHA256" "$archive" | sha256sum -c -
printf '%s  %s\n' "$M8A_ROOTFS_SHA256" out/kvmd/artifacts/rootfs.tar.gz | sha256sum -c -
sha256sum -c build/ubuntu/m5-artifacts.sha256
sha256sum -c build/ustreamer/m7-artifacts.sha256
printf '%s  %s\n' "$KVMD_PATCH_SHA256" build/kvmd/video-only.patch | sha256sum -c -
printf '%s  %s\n' "$WEB_PATCH_SHA256" build/kvmd-web/web-auth.patch | sha256sum -c -
sudo -n docker image inspect "$BUILDER_IMAGE" > out/kvmd-msd/builder-image.json
actual_builder=$(python3 -c 'import json; print(json.load(open("out/kvmd-msd/builder-image.json"))[0]["Id"])')
test "$actual_builder" = "$USTREAMER_BUILDER_ID" || { echo 'Unexpected builder image ID' >&2; exit 1; }
if [ "$mode" = rootfs ]; then
    sha256sum -c build/kvmd-msd/package.sha256
fi
sudo -n docker run --rm --privileged -e "SOURCE_DATE_EPOCH=$SOURCE_DATE_EPOCH" \
  -v "$repo:/work" "$BUILDER_IMAGE" \
  bash -c 'cp /work/build/kvmd-msd/in-container.sh /tmp/ustreamer-build.sh; exec unshare --user --map-users=0,0,65536 --map-groups=0,0,65536 --mount --pid --fork --mount-proc bash /tmp/ustreamer-build.sh "$1"' -- "$mode"
sudo -n chown -R "$(id -u):$(id -g)" out/kvmd-msd/artifacts
