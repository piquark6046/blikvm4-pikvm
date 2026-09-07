#!/usr/bin/env python3
"""M8-D upgrade payload, inheriting M8-C network and M8-B authentication."""
from pathlib import Path
import runpy
import sys
import shutil
source, pkg = map(Path, sys.argv[1:])
repo=Path(__file__).resolve().parents[2]
runpy.run_path(str(repo/'build/kvmd-web/package.py'), run_name='__main__')
def copy(src, dst, mode=0o644):
    p=pkg/dst;p.parent.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(src,p);p.chmod(mode)
control=pkg/'DEBIAN/control'
text=control.read_text().replace('4.213-1blikvm2','4.213-1blikvm3').replace('python3-pyotp\n','python3-pyotp, python3-xlib (= 0.33-5), libxkbcommon0 (= 1.13.1-1), xkb-data (= 2.46-2)\n').replace('M8-B loopback web authentication','M8-D authenticated HID and LAN web')
control.write_text(text)
copy(repo/'build/kvmd-lan/nginx.conf','etc/kvmd/nginx/nginx.conf')
copy(repo/'build/kvmd-hid/hid.yaml','etc/kvmd/override.d/90-hid.yaml')
copy(repo/'build/kvmd-hid/hid.conf','usr/lib/systemd/system/kvmd.service.d/hid.conf')
copy(repo/'build/kvmd-hid/blikvm-gadget.service','usr/lib/systemd/system/blikvm-gadget.service')
copy(repo/'build/kvmd-hid/resolve-hid.py','usr/lib/kvmd-hid/resolve-hid',0o755)
shutil.copytree(source/'contrib/keymaps',pkg/'usr/share/kvmd/keymaps')
d=pkg/'usr/lib/kvmd-hid/descriptors';d.mkdir(parents=True)
hid=runpy.run_path(str(repo/'lab/hidlab.py'))
(d/'keyboard').write_bytes(hid['REPORT_DESCRIPTOR'])
for role in ('absolute','relative'):
    (d/role).write_bytes(bytes.fromhex((repo/f'initramfs/hid-{role}-mouse.report.hex').read_text()))
p=pkg/'DEBIAN/postinst';p.write_text(p.read_text().replace('    systemctl enable kvmd.service','    systemctl enable blikvm-gadget.service\n    systemctl enable kvmd.service'))
p=pkg/'DEBIAN/conffiles';p.write_text(p.read_text()+'/etc/kvmd/override.d/90-hid.yaml\n')
