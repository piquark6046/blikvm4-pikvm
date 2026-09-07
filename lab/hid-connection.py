#!/usr/bin/env python3
"""Archive an explicitly prompted physical connection window; never fake D9."""
import json
from pathlib import Path
import runpy
import subprocess
import time
HERE=Path(__file__).resolve().parent
G4=runpy.run_path(str(HERE/'storagelab.py'));G1=G4['G1']
root=Path.cwd();out=root/'qualification/connection-first';out.mkdir(exist_ok=False)
class Recorder:
    path=out
    def save_text(self,name,text):(out/name).write_text(text)
r=Recorder();monitor=G1['HostMonitor'](r);result={'result':'failed','d9_qualified':False}
try:
    monitor.start();G1['host_logs'](r,'before')
    initial=G1['keyboard_device']()
    result['initially_present']=initial is not None
    (out/'ready.json').write_text(json.dumps({'ready':True,'initially_present':initial is not None}))
    print('READY TO RECONNECT USB-PC',flush=True)
    if initial is not None:G4['wait_device'](False,900)
    device=G4['wait_device'](True,900)
    result['device']=G4['details'](device)
    result['descriptors']=G4['exact_descriptors'](device,r,'connected')
    G1['host_logs'](r,'after')
    result['result']='connected'
    # Initial absence cannot prove a present -> absent -> present D9 sequence.
except Exception as e:result['error']=str(e)
finally:
    monitor.stop();(out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result),flush=True)
