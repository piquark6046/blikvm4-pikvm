#!/bin/bash
# Each invocation builds in a fresh local clone with its own ignored out/ tree.
set -euo pipefail
repo=$(cd "$(dirname "$0")/../.." && pwd)
test "${1:-}" = --output && test -n "${2:-}" && test $# -eq 2 || {
    echo 'usage: build.sh --output out/<new-directory>' >&2; exit 2;
}
dest=$(realpath -m "$2")
case "$dest" in "$repo"/out/*) ;; *) echo 'output must be under repository out/' >&2; exit 2;; esac
test ! -e "$dest" || { echo 'output already exists' >&2; exit 2; }
test -z "$(git -C "$repo" status --porcelain)" || { echo 'source checkout is dirty' >&2; exit 2; }
mkdir -p "$dest"
git clone --quiet --no-hardlinks --local "$repo" "$dest/source"
test "$(git -C "$dest/source" rev-parse HEAD)" = "$(git -C "$repo" rev-parse HEAD)"
"$dest/source/build/release/build-in-clone.sh"
cp -a "$dest/source/out/release/candidate" "$dest/public"
