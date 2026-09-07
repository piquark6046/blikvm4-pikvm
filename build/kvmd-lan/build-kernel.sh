#!/bin/bash
# Explicit, independently invoked exception; never called by the rootfs builder.
set -euo pipefail
repo=$(cd "$(dirname "$0")/../.." && pwd)
source "$repo/build/versions.env"
cd "$repo"
mkdir -p out/kvmd-lan/kernel
sha256sum -c build/ustreamer/m7-artifacts.sha256
sudo -n docker run --rm --user "$(id -u):$(id -g)" \
  --env JOBS="${JOBS:-3}" -v "$repo:/work" "$TOOLCHAIN_IMAGE" bash -euc '
  src=/work/out/src/linux-7.2.3
  obj=/work/out/build/linux-7.2.3
  dest=/work/out/kvmd-lan/kernel
  cat /work/out/kvmd-web/artifacts/linux.config /work/build/kvmd-lan/linux-firewall.config > "$dest/input.config"
  input_hash=$(sha256sum "$dest/input.config" | cut -d" " -f1)
  if ! test -f "$obj/.config-input.sha256" || test "$(cat "$obj/.config-input.sha256")" != "$input_hash"; then
    "$src/scripts/kconfig/merge_config.sh" -m -O "$obj" /work/out/kvmd-web/artifacts/linux.config /work/build/kvmd-lan/linux-firewall.config
    make -C "$src" O="$obj" olddefconfig
    echo "$input_hash" > "$dest/input.sha256"
    echo "$input_hash" > "$obj/.config-input.sha256"
  fi
  make -C "$src" O="$obj" -j"$JOBS" Image
  cp "$obj/arch/arm64/boot/Image" "$dest/Image"
  cp "$obj/.config" "$dest/linux.config"
  cp /work/out/build/artifacts/sun50i-h616-blikvm-v4.dtb "$dest/"
  "$src/scripts/diffconfig" /work/out/kvmd-web/artifacts/linux.config "$dest/linux.config" > "$dest/config-delta.txt"
  cd "$dest"
  sha256sum Image linux.config sun50i-h616-blikvm-v4.dtb > SHA256SUMS
  '
sha256sum -c build/ustreamer/m7-artifacts.sha256
