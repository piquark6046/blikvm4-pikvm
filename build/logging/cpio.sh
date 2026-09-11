#!/bin/bash
set -euo pipefail
# Run within the pinned build container, with only the candidate directory mounted.
mkdir /tmp/logging-root
cd /tmp/logging-root
tar --numeric-owner -xpf /candidate/rootfs.tar.gz
find . -xdev -exec touch -h -d @1788652800 {} +
find . -xdev -print0 | LC_ALL=C sort -z | cpio --null -o -H newc --reproducible 2>/dev/null | gzip -n -9 > /candidate/initramfs.cpio.gz
