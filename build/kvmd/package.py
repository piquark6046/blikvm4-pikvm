#!/usr/bin/env python3
"""Assemble a video-only Debian payload from verified, patched source."""
from pathlib import Path
import shutil
import sys
source, pkg = map(Path, sys.argv[1:])
project = Path('/work/build/kvmd')
def put(name, text, mode=0o644):
    path = pkg/name; path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text); path.chmod(mode)
def copy(src, name):
    path=pkg/name; path.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(src,path)
# Include importable code, but no extra entrypoints, platform services, firmware or web assets.
shutil.copytree(source/'kvmd', pkg/'usr/lib/python3/dist-packages/kvmd')
copy(source/'LICENSE', 'usr/share/doc/kvmd-video/copyright')
copy(project/'main.yaml','usr/lib/kvmd/main.yaml')
copy(project/'kvmd.service','usr/lib/systemd/system/kvmd.service')
put('usr/bin/kvmd','#!/usr/bin/python3\nfrom kvmd.apps.kvmd import main\nmain()\n',0o755)
put('usr/lib/kvmd/platform','PIKVM_MODEL=blikvm-v4\nPIKVM_VIDEO=ms2131-mjpeg\nPIKVM_BOARD=allwinner-h616\n')
put('etc/kvmd/meta.yaml','server:\n    host: BliKVM v4\n')
put('etc/kvmd/override.yaml','{}\n')
(pkg/'etc/kvmd/override.d').mkdir(parents=True)
put('usr/lib/sysusers.d/kvmd-video.conf','u kvmd - "BliKVM video API" /nonexistent /usr/sbin/nologin\n')
# Same frozen device identity/permissions; replace only the service activation request.
rules=Path('/work/build/ustreamer/99-blikvm-video.rules').read_text().replace('ustreamer.service','kvmd.service')
put('usr/lib/udev/rules.d/99-blikvm-video.rules',rules)
put('DEBIAN/control','''Package: kvmd-video
Version: 4.213-1blikvm1
Architecture: arm64
Maintainer: BliKVM Port <noreply@localhost>
Depends: python3 (>= 3.14), python3 (<< 3.15), python3-yaml, python3-ruamel.yaml, python3-aiohttp, python3-aiofiles, python3-setproctitle, python3-pygments, python3-evdev, python3-pil, ustreamer (= 6.65-1blikvm2), systemd, udev
Replaces: ustreamer (<= 6.65-1blikvm2)
Description: Pinned BliKVM M8-A local Unix API and native MJPEG video daemon
''')
put('DEBIAN/postinst','''#!/bin/sh
set -e
if [ "$1" = configure ]; then
    systemd-sysusers /usr/lib/sysusers.d/kvmd-video.conf
    if [ -d /run/systemd/system ]; then systemctl stop ustreamer.service; fi
    systemctl disable ustreamer.service
    systemctl mask ustreamer.service
    systemctl enable kvmd.service
    if [ -d /run/systemd/system ]; then
        systemctl daemon-reload
        udevadm control --reload
        systemctl start kvmd.service
    fi
fi
''',0o755)
put('DEBIAN/prerm','''#!/bin/sh
set -e
if [ -d /run/systemd/system ]; then systemctl stop kvmd.service; fi
''',0o755)
put('DEBIAN/postrm','''#!/bin/sh
set -e
if [ "$1" = remove ] || [ "$1" = purge ]; then systemctl disable kvmd.service || true; fi
if [ -d /run/systemd/system ]; then systemctl daemon-reload; fi
''',0o755)
