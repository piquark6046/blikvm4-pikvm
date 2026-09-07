#!/usr/bin/env python3
"""Archive the target inventory associated with an exact RAM boot."""
import argparse
import json
from pathlib import Path
import subprocess
p=argparse.ArgumentParser();p.add_argument('--boot-result',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
known=Path(json.loads(a.boot_result.read_text())['run_directory'])/'known_hosts'
assert not a.output.exists()
s=['ssh','-i','/home/user/.local/share/blikvm-m7/id_ed25519','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-o','UserKnownHostsFile='+str(known),'blikvm@192.168.88.2','sudo -n python3 -']
r=subprocess.run(s,input=Path(__file__).with_name('hid-inventory.py').read_text(),text=True,capture_output=True,timeout=60)
a.output.write_text(r.stdout);a.output.with_suffix('.stderr').write_text(r.stderr)
assert r.returncode==0,json.loads(r.stdout).get('error')
