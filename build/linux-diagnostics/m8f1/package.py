#!/usr/bin/env python3
"""Package diagnostic kernel with the exact Run 03 enrolled userspace/DTB."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

root = Path('out/m8f1')
artifacts = root/'artifacts'
artifacts.mkdir(exist_ok=False)
base = Path('out/m8f0/uvc-candidate-02/artifacts')
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
reference = json.loads((base/'manifest.json').read_text())
for name in ('initramfs.cpio.gz', 'sun50i-h616-blikvm-v4.dtb'):
    assert sha(base/name) == reference['artifacts'][name]['sha256']
    shutil.copyfile(base/name, artifacts/name)
shutil.copyfile(root/'objects/arch/arm64/boot/Image', artifacts/'Image')
shutil.copyfile(root/'objects/.config', artifacts/'linux.config')
def config(path):
    d = {}
    for line in path.read_text().splitlines():
        if line.startswith('CONFIG_'):
            k,v=line.split('=',1); d[k]=v
        elif line.startswith('# CONFIG_') and line.endswith(' is not set'):
            d[line.split()[1]]='n'
    return d
before=config(base/'linux.config'); after=config(artifacts/'linux.config')
delta={k:{'before':before.get(k),'after':after.get(k)} for k in sorted(before.keys()|after.keys()) if before.get(k)!=after.get(k)}
assert set(delta) == {'CONFIG_LOCALVERSION','CONFIG_PROC_PAGE_MONITOR','CONFIG_SLUB_DEBUG','CONFIG_SLUB_DEBUG_ON','CONFIG_STACKDEPOT','CONFIG_STACKDEPOT_MAX_FRAMES','CONFIG_STACKTRACE'}
assert after['CONFIG_SLUB_DEBUG_ON']=='n'
manifest={'source':{'commit':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'dirty':True},'diagnostic':True,'qualification':False,'purpose':'M8-F1 targeted memory attribution','configuration_delta':delta,'userspace':'byte-identical Run 03 enrolled image','production_fix':False,'artifacts':{p.name:{'name':p.name,'size':p.stat().st_size,'sha256':sha(p)} for p in artifacts.iterdir()},'unchanged_uvc_source_sha256':{n:sha(Path('out/m8f0/uvc-candidate-02/source/drivers/media/usb/uvc')/n) for n in ['uvc_driver.c','uvc_video.c','uvc_queue.c','uvcvideo.h']}}
(artifacts/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(json.dumps(manifest,indent=2))
