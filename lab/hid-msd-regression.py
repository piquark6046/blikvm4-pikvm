#!/usr/bin/env python3
"""Use the accepted G4 host read-only checks without any kvmd MSD API."""
import argparse
import json
from pathlib import Path
import runpy
H=runpy.run_path(str(Path(__file__).with_name('hid-api-hil.py')))
p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args()
a.output.mkdir(parents=True,exist_ok=False);r=H['Recorder'](a.output)
result={'result':'failed'}
try:
 d=H['G4']['wait_device'](True,20)
 result['descriptors']=H['G4']['exact_descriptors'](d,r,'msd')
 result['storage']=H['G4']['storage_test'](d,r,'regression')
 result['result']='passed'
except Exception as e:result['error']=str(e)
r.save_text('result.json',json.dumps(result,indent=2)+'\n')
raise SystemExit(result['result']!='passed')
