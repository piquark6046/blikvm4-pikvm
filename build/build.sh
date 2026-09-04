#!/bin/bash
set -euo pipefail

repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
source "$repo/build/versions.env"
jobs=${JOBS:-3}

mkdir -p "$repo/out/downloads" "$repo/out/src" "$repo/out/build"

fetch_verified() {
    local url=$1
    local destination=$2
    local expected=$3
    if test -f "$destination" \
       && printf '%s  %s\n' "$expected" "$destination" | sha256sum -c - >/dev/null; then
        return
    fi
    local temporary="${destination}.part"
    curl -fL --retry 3 --connect-timeout 20 -o "$temporary" "$url"
    printf '%s  %s\n' "$expected" "$temporary" | sha256sum -c -
    mv "$temporary" "$destination"
}

fetch_verified \
    "https://cdn.kernel.org/pub/linux/kernel/v7.x/linux-$LINUX_VERSION.tar.xz" \
    "$repo/out/downloads/linux-$LINUX_VERSION.tar.xz" \
    "$LINUX_SHA256"
fetch_verified \
    "https://dl-cdn.alpinelinux.org/alpine/v${ALPINE_VERSION%.*}/releases/aarch64/alpine-minirootfs-$ALPINE_VERSION-aarch64.tar.gz" \
    "$repo/out/downloads/alpine-minirootfs-$ALPINE_VERSION-aarch64.tar.gz" \
    "$ALPINE_SHA256"

if ! test -f "$repo/out/src/linux-$LINUX_VERSION/Makefile"; then
    tar -C "$repo/out/src" -xf "$repo/out/downloads/linux-$LINUX_VERSION.tar.xz"
fi

docker=(docker)
if ! docker info >/dev/null 2>&1; then
    docker=(sudo -n docker)
fi

if ! "${docker[@]}" image inspect "$TOOLCHAIN_IMAGE" >/dev/null 2>&1; then
    "${docker[@]}" build \
        --build-arg "TOOLCHAIN_BASE=$TOOLCHAIN_BASE" \
        --file "$repo/build/Containerfile" \
        --tag "$TOOLCHAIN_IMAGE" \
        "$repo/build"
fi

"${docker[@]}" run --rm \
    --security-opt label=disable \
    --user "$(id -u):$(id -g)" \
    --env HOME=/tmp \
    --env "JOBS=$jobs" \
    --volume "$repo:/work" \
    --workdir /work \
    "$TOOLCHAIN_IMAGE" \
    /work/build/in-container-build.sh

if test -f "$repo/artifacts/vendor/Image"; then
    "$repo/out/src/linux-$LINUX_VERSION/scripts/extract-ikconfig" \
        "$repo/artifacts/vendor/Image" \
        > "$repo/out/build/vendor-5.19.4.config"
fi

toolchain_id=$("${docker[@]}" image inspect --format '{{.Id}}' "$TOOLCHAIN_IMAGE")
python3 "$repo/build/write-manifest.py" "$toolchain_id"

printf 'Linux %s artifacts are in %s\n' \
    "$LINUX_VERSION" "$repo/out/build/artifacts"
