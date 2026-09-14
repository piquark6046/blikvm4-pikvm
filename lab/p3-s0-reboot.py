#!/usr/bin/env python3
"""Exactly one ordinary preparation reboot, gated by archived-state VM review."""
import ast,hashlib,json,os,subprocess,time
from pathlib import Path
B=Path('/var/lib/blikvm-p3-s0')
os.umask(0o077)
assert hashlib.sha256((B/'boot-invariant.json').read_bytes()).hexdigest()=='9cf77f9c6931c383657cbe625c2f640ba77da0ccf7c851b986d056e51280d899'
assert json.loads((B/'vm-current-replay.json').read_text())['result']=='S0_CURRENT_EMPTY_VERIFIED'
events=[json.loads(l) for l in (B/'preparation-reboot-uart/events.jsonl').read_text().splitlines()]
assert any(e['event']=='uart_open' for e in events)
ready=json.loads((B/'preparation-reboot-uart/ready.json').read_text());os.kill(ready['pid'],0)
base=Path('/var/lib/blikvm-p3-h5r1/controller/functional-preparation')
ssh=next(ast.literal_eval(n.value) for n in ast.parse((base/'collect.py').read_text()).body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='ssh' for t in n.targets))
def command(c):return subprocess.run(ssh+[c],capture_output=True,text=True,timeout=20)
old=json.loads((B/'current-empty-complete/inventory/target.json').read_text())['boot_id']
p=command('cat /proc/sys/kernel/random/boot_id');assert p.returncode==0 and p.stdout.strip()==old
with (B/'REBOOT_REQUESTED.json').open('x') as f:json.dump(dict(scope='P3-S0 preparation reboot',old_boot_id=old,wall_ns=time.time_ns(),qualification_credit=0,accepted_cycles=0),f)
p=command('sudo -n systemctl reboot')
(B/'reboot-command.json').write_text(json.dumps(dict(returncode=p.returncode,stdout=p.stdout,stderr=p.stderr)))
assert p.returncode in (0,255)
deadline=time.monotonic()+150;probes=[]
while time.monotonic()<deadline:
 time.sleep(2)
 p=command('cat /proc/sys/kernel/random/boot_id; systemctl is-active blikvm-gadget blikvm-msd-helper kvmd nginx')
 probes.append(dict(wall_ns=time.time_ns(),returncode=p.returncode,stdout=p.stdout,stderr=p.stderr))
 (B/'reboot-readiness.json').write_text(json.dumps(probes,indent=2))
 lines=p.stdout.splitlines()
 if p.returncode==0 and len(lines)==5 and lines[0]!=old and lines[1:]==['active']*4:break
else:raise RuntimeError('P3-S0 autonomous reboot readiness failed; no retry')
p=subprocess.run(['python3','/tmp/p3-s0-snapshot-v2.py',str(B/'fresh-boot')],capture_output=True,text=True,timeout=300)
(B/'fresh-boot-transport.json').write_text(json.dumps(dict(returncode=p.returncode,stdout=p.stdout,stderr=p.stderr)))
assert p.returncode==0
print('ONE_PREPARATION_REBOOT_COMPLETE_PENDING_INVARIANT_REVIEW',flush=True)
