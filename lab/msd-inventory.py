#!/usr/bin/python3
"""Read-only E inventory on target, retaining M8-D policy/video/HID checks."""
import hashlib
import json
from pathlib import Path
import runpy
import subprocess
import contextlib
import io

# Retain every inherited check, advancing only the exact package version.
source=Path('/run/m8e-hid-inventory.py').read_text()
old="== '4.213-1blikvm3'"
assert source.count(old)==1
source=source.replace(old,"== '4.213-1blikvm4'")
out=io.StringIO()
with contextlib.redirect_stdout(out):
    try:
        exec(compile(source,'/run/m8e-hid-inventory.py','exec'), {'__name__':'__main__'})
    except SystemExit:
        pass
result=json.loads(out.getvalue())
try:
    assert result['result']=='passed',result.get('error')
    helper=runpy.run_path('/usr/lib/kvmd-msd/media-helper')
    lun=helper['validate']();helper['catalog']()
    result['msd_lun']={n:(lun/n).read_text().strip() for n in ('file','ro','cdrom','removable','nofua','inquiry_string')}
    result['msd_image_sha256']=hashlib.sha256(Path('/usr/share/kvmd-msd/images/g4-storage.img').read_bytes()).hexdigest()
    assert result['msd_image_sha256']==helper['G4_HASH']
    result['helper_unit']=subprocess.check_output(['systemctl','cat','blikvm-msd-helper'],text=True)
    assert subprocess.check_output(['systemctl','is-active','blikvm-msd-helper'],text=True).strip()=='active'
    assert not Path('/usr/bin/kvmd-otg').exists()
    result['msd_journal']=subprocess.check_output(['journalctl','-b','-u','kvmd','-u','blikvm-msd-helper','--no-pager'],text=True)
    bad=[line for line in result['msd_journal'].splitlines() if 'plugins.msd' in line and any(x in line for x in ('ERROR','CRITICAL','Traceback'))]
    assert not bad,bad
    result['failed_units']=subprocess.check_output(['systemctl','--failed','--no-legend','--plain'],text=True)
    assert not result['failed_units'].strip()
except Exception as ex:result.update(result='failed',error=str(ex))
print(json.dumps(result,indent=2));raise SystemExit(result['result']!='passed')
