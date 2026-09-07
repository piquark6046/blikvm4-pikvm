#!/usr/bin/python3
"""Read the running helper's real namespace and capabilities without mutations."""
import json,subprocess
from pathlib import Path
r={'result':'failed'}
try:
    pid=int(subprocess.check_output(['systemctl','show','blikvm-msd-helper','-p','MainPID','--value'],text=True))
    assert pid>1
    status=Path(f'/proc/{pid}/status').read_text();r['status']=status
    fields={l.split(':',1)[0]:l.split(':',1)[1].strip() for l in status.splitlines() if ':' in l}
    assert int(fields['CapBnd'],16)==1 and int(fields['CapEff'],16)==1
    assert fields['NoNewPrivs']=='1'
    mounts=Path(f'/proc/{pid}/mountinfo').read_text();r['mountinfo']=mounts
    lun='/sys/kernel/config/usb_gadget/blikvm_m5/functions/mass_storage.g4/lun.0'
    entries=[l.split() for l in mounts.splitlines()]
    config=[x for x in entries if x[4].startswith('/sys/kernel/config') and 'rw' in x[5].split(',')]
    assert {x[4] for x in config}=={lun+'/file',lun+'/forced_eject'},config
    parent=max([x for x in entries if (lun+'/ro').startswith(x[4].rstrip('/')+'/')],key=lambda x:len(x[4]))
    assert 'ro' in parent[5].split(','),parent
    r['writable_configfs']=[x[4] for x in config]
    r['result']='passed'
except Exception as ex:r['error']=str(ex)
print(json.dumps(r,indent=2));raise SystemExit(r['result']!='passed')
