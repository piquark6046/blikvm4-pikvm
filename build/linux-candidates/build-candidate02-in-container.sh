#!/bin/bash
set -euo pipefail
src=/work/out/m8f0/uvc-candidate-02/source
obj=/work/out/m8f0/uvc-candidate-02/objects
mkdir -p "$obj"
if ! test -f "$obj/.config"; then
 cp /work/out/kvmd-msd/artifacts/linux.config "$obj/.config"
 "$src/scripts/config" --file "$obj/.config" --set-str LOCALVERSION '-blikvm-v4-m8f0-ms2131c2'
fi
export KBUILD_BUILD_TIMESTAMP=1970-01-01T00:00:00Z KBUILD_BUILD_USER=builder KBUILD_BUILD_HOST=blikvm KBUILD_BUILD_VERSION=1
make -C "$src" O="$obj" ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu- olddefconfig
make -C "$src" O="$obj" ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu- -j3 Image
