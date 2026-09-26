#!/bin/bash
# Produce an offline-verifiable source-built bootloader candidate; no HIL claim.
set -euo pipefail
repo=$(cd "$(dirname "$0")/../.." && pwd)
root="$repo/out/release/bootloader"
test ! -e "$root" || { echo 'bootloader output already exists' >&2; exit 2; }
mkdir -p "$root"
uboot_commit=88dc2788777babfd6322fa655df549a019aa1e69
tfa_commit=1d5aa939bc8d3d892e2ed9945fa50e36a1a924cc
git clone --depth 1 --branch v2026.04 https://github.com/u-boot/u-boot.git "$root/u-boot"
git clone --depth 1 --branch v2.14.0 https://github.com/ARM-software/arm-trusted-firmware.git "$root/tf-a"
test "$(git -C "$root/u-boot" rev-parse HEAD)" = "$uboot_commit"
test "$(git -C "$root/tf-a" rev-parse HEAD)" = "$tfa_commit"
cp "$repo/build/release/sun50i-h616-blikvm-v4.dts" "$root/u-boot/dts/upstream/src/arm64/allwinner/"
sed -e 's@sun50i-h616-orangepi-zero2@sun50i-h616-blikvm-v4@' \
    -e 's/^CONFIG_AXP305_POWER=y$/CONFIG_AXP313_POWER=y/' \
    "$root/u-boot/configs/orangepi_zero2_defconfig" > "$root/u-boot/configs/blikvm_v4_defconfig"
test "$(grep -Fxc -- 'CONFIG_AXP313_POWER=y' "$root/u-boot/configs/blikvm_v4_defconfig")" = 1
docker_cmd=(docker)
if ! docker info >/dev/null 2>&1; then docker_cmd=(sudo -n docker); fi
boot_builder=blikvm-release-bootloader:20260904
"${docker_cmd[@]}" build -f "$repo/build/release/BootloaderContainerfile" \
    -t "$boot_builder" "$repo/build/release"
"${docker_cmd[@]}" run --rm --user "$(id -u):$(id -g)" -e JOBS="${JOBS:-2}" \
    -v "$repo:/work" "$boot_builder" bash -euc '
    cd /work/out/release/bootloader/tf-a
    make -j"$JOBS" CROSS_COMPILE=aarch64-linux-gnu- PLAT=sun50i_h616 DEBUG=1 \
        BUILD_MESSAGE_TIMESTAMP='"'"'"1970-01-01T00:00:00Z"'"'"' bl31
    cd /work/out/release/bootloader/u-boot
    make CROSS_COMPILE=aarch64-linux-gnu- blikvm_v4_defconfig
    make -j"$JOBS" CROSS_COMPILE=aarch64-linux-gnu- BL31=/work/out/release/bootloader/tf-a/build/sun50i_h616/debug/bl31.bin
    '
cp "$root/u-boot/u-boot-sunxi-with-spl.bin" "$root/u-boot-sunxi-with-spl.bin"
python3 - "$root" "$uboot_commit" "$tfa_commit" <<'PY'
import hashlib,json,sys
from pathlib import Path
r=Path(sys.argv[1]);image=r/'u-boot-sunxi-with-spl.bin'
data=image.read_bytes()
if not data or len(data)>4*1024*1024-8192:
    raise SystemExit('source-built bootloader does not fit the 4 MiB boot region')
digest=hashlib.sha256(data).hexdigest()
(r/'layout.json').write_text(json.dumps({
    'type':'source-built-candidate',
    'u_boot_commit':sys.argv[2],'tf_a_commit':sys.argv[3],
    'bootloader_extents':[{'name':image.name,'offset':8192,'size':len(data),'sha256':digest}],
},indent=2,sort_keys=True)+'\n')
print(digest)
PY
