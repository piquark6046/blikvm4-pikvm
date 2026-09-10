#!/bin/bash
set -euo pipefail
src=/work/out/m8f0/uvc-candidate-02/source
obj=/work/out/m8f1/objects
"$src/scripts/config" --file "$obj/.config" --enable PROC_PAGE_MONITOR --enable SLUB_DEBUG --disable SLUB_DEBUG_ON --set-str LOCALVERSION '-blikvm-v4-m8f1-memory'
export KBUILD_BUILD_TIMESTAMP=1970-01-01T00:00:00Z KBUILD_BUILD_USER=builder KBUILD_BUILD_HOST=blikvm KBUILD_BUILD_VERSION=1
make -C "$src" O="$obj" ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu- olddefconfig
make -C "$src" O="$obj" ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu- -j4 Image
