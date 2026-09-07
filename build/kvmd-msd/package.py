#!/usr/bin/env python3
"""M8-E package layered over the frozen M8-D payload."""
from pathlib import Path
import json
import runpy
import shutil
import sys
source, pkg = map(Path, sys.argv[1:])
repo = Path(__file__).resolve().parents[2]
runpy.run_path(str(repo/'build/kvmd-hid/package.py'), run_name='__main__')
def copy(src, dst, mode=0o644):
    p = pkg/dst
    p.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, p)
    p.chmod(mode)
p = pkg/'DEBIAN/control'
p.write_text(p.read_text().replace('4.213-1blikvm3','4.213-1blikvm4').replace('M8-D authenticated HID and LAN web','M8-E authenticated read-only media and HID'))
copy(repo/'build/kvmd-msd/media-helper.py','usr/lib/kvmd-msd/media-helper',0o755)
copy(repo/'build/kvmd-msd/helper.service','usr/lib/systemd/system/blikvm-msd-helper.service')
copy(repo/'build/kvmd-msd/msd.conf','usr/lib/systemd/system/kvmd.service.d/msd.conf')
copy(repo/'build/kvmd-msd/msd.yaml','etc/kvmd/override.d/95-msd.yaml')
image = runpy.run_path(str(repo/'build/make-storage-image.py'))
root = pkg/'usr/share/kvmd-msd'
(root/'images').mkdir(parents=True)
(root/'images/g4-storage.img').write_bytes(image['build_image']())
(root/'images/g4-storage.img').chmod(0o444)
m = image['manifest']()
(root/'catalog.json').write_text(json.dumps({'g4-storage.img':{'size':m['size'],'sha256':m['sha256']}},indent=2)+'\n')
(root/'catalog.json').chmod(0o444)
p=pkg/'DEBIAN/conffiles';p.write_text(p.read_text()+'/etc/kvmd/override.d/95-msd.yaml\n')
p=pkg/'DEBIAN/postinst';p.write_text(p.read_text().replace('    systemctl enable kvmd.service','    systemctl enable blikvm-msd-helper.service\n    systemctl enable kvmd.service'))
# Hide excluded presentation even before JS state initialization. Keep IDs for upstream code.
p=pkg/'usr/share/kvmd/web/kvm/index.html';s=p.read_text()
s=s.replace('<td><a target="_blank" href="https://docs.pikvm.org/msd">Mode</a>:</td>', '<td>Read-only flash media</td>')
s=s.replace('<td>Writable:</td>','<td></td>')
for id in ('msd-mode-radio-0','msd-mode-radio-1','msd-rw-switch','msd-download-button','msd-remove-button','msd-select-new-button','msd-reset-button','msd-new-sub'):
 s=s.replace('id="'+id+'"', 'style="display:none" id="'+id+'"')
for id in ('msd-mode-radio-0','msd-mode-radio-1','msd-rw-switch'):
 s=s.replace('for="'+id+'"', 'style="display:none" for="'+id+'"')
p.write_text(s)
