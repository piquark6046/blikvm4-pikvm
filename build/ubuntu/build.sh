#!/bin/bash
set -euo pipefail
repo=$(cd "$(dirname "$0")/../.." && pwd)
source "$repo/build/ubuntu/versions.env"
mode=${1:-packages}
case "$mode" in packages|finalize) ;; *) echo 'usage: build.sh packages | finalize /absolute/external/key.pub' >&2; exit 2;; esac
cd "$repo"
mkdir -p out/ubuntu/downloads
sha256sum -c build/ubuntu/m5-artifacts.sha256
download=out/ubuntu/downloads
if [ "$mode" = packages ]; then
    for name in SHA256SUMS SHA256SUMS.gpg "$UBUNTU_ARCHIVE"; do
        if ! test -f "$download/$name"; then
            curl -fL --retry 3 --connect-timeout 20 --max-time 600 "$UBUNTU_URL/$name" -o "$download/$name.part"
            mv "$download/$name.part" "$download/$name"
        fi
    done
    # Trust the Build VM distribution keyring, never a key supplied by the archive.
    cp /usr/share/keyrings/ubuntu-archive-keyring.gpg "$download/ubuntu-archive-keyring.gpg"
    gpgv --status-fd 1 --keyring "$download/ubuntu-archive-keyring.gpg" \
        "$download/SHA256SUMS.gpg" "$download/SHA256SUMS" > "$download/signature-status.log" 2> "$download/signature.log"
    grep -q "^\[GNUPG:\] VALIDSIG $UBUNTU_SIGNER " "$download/signature-status.log"
    grep -Fx "$UBUNTU_SHA256 *$UBUNTU_ARCHIVE" "$download/SHA256SUMS"
    printf '%s  %s\n' "$UBUNTU_SHA256" "$download/$UBUNTU_ARCHIVE" | sha256sum -c -
    sudo -n docker build --build-arg "BUILDER_BASE=$BUILDER_BASE" -f build/ubuntu/Containerfile -t "$BUILDER_IMAGE" build/ubuntu
    sudo -n docker image inspect "$BUILDER_IMAGE" > out/ubuntu/builder-image.json
    sudo -n docker run --rm --privileged --env "SOURCE_DATE_EPOCH=$SOURCE_DATE_EPOCH" \
        -v "$repo:/work" "$BUILDER_IMAGE" \
        unshare --user --map-users=0,0,65536 --map-groups=0,0,65536 \
        --mount --pid --fork --mount-proc /work/build/ubuntu/in-container.sh packages
else
    key=$(realpath "${2:?public key file outside Git required}")
    case "$key" in "$repo"/*) echo 'public key must be outside repository' >&2; exit 2;; esac
    # ssh-keygen -l also accepts private-key files. Reject those before mounting
    # the input into any container; this interface accepts one public key only.
    python3 - "$key" <<'PY'
import sys
from pathlib import Path
lines = Path(sys.argv[1]).read_text().strip().splitlines()
if len(lines) != 1 or len(lines[0].split()) < 2 or not lines[0].split()[0].startswith(('ssh-', 'ecdsa-')):
    raise SystemExit('expected one OpenSSH public key, never a private key')
PY
    ssh-keygen -lf "$key" >/dev/null
    sudo -n docker run --rm --privileged --env "SOURCE_DATE_EPOCH=$SOURCE_DATE_EPOCH" \
        -v "$repo:/work" -v "$key:/provision/authorized_keys:ro" \
        "$BUILDER_IMAGE" \
        unshare --user --map-users=0,0,65536 --map-groups=0,0,65536 \
        --mount --pid --fork --mount-proc /work/build/ubuntu/in-container.sh finalize
    sudo -n chown -R "$(id -u):$(id -g)" "$repo/out/ubuntu/artifacts"
    python3 "$repo/build/ubuntu/write-manifest.py"
fi
