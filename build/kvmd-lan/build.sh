#!/bin/bash
set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)/build/release/verify.sh"
cd "$(dirname "$0")/../.."
source build/ubuntu/versions.env
source build/ustreamer/versions.env
mkdir -p out/kvmd-lan/artifacts
sudo -n docker image inspect "$BUILDER_IMAGE" > out/kvmd-lan/builder-image.json
actual=$(python3 -c 'import json; print(json.load(open("out/kvmd-lan/builder-image.json"))[0]["Id"])')
release_verify_builder "$actual" "$USTREAMER_BUILDER_ID"
sudo -n docker run --rm --privileged -e "BLIKVM_RELEASE_BUILD=${BLIKVM_RELEASE_BUILD:-0}" -v "$PWD:/work" "$BUILDER_IMAGE" \
 bash -c 'cp /work/build/kvmd-lan/in-container.sh /tmp/m8c-build.sh; exec unshare --user --map-users=0,0,65536 --map-groups=0,0,65536 --mount --pid --fork --mount-proc bash /tmp/m8c-build.sh'
sudo -n chown -R "$(id -u):$(id -g)" out/kvmd-lan/artifacts
