#!/usr/bin/env python3
"""Read-only failure review plus a post-seal UID audit; never retries Chromium."""
import json
import os
from pathlib import Path
import runpy
import subprocess

H=runpy.run_path(str(Path(__file__).with_name('p3-h3-boundary.py')))
F=runpy.run_path(str(Path(__file__).with_name('p3-h3-preflight.py')))
BASE,LEGACY=H['BASE'],H['LEGACY'];read,publish,require=H['read_json'],H['publish'],H['require']
require(os.geteuid()==0,'root required');os.umask(0o077);H['browser_idle']()
run=BASE/'controller/chromium-preflight-001';failed=read(run/'result.json')
require(failed['result']=='FAILED' and (BASE/'controller/FAILED.json').exists(),'failed latch required')
review=run/'failure-review';review.mkdir(mode=0o700)
config=read(BASE/'controller/config.json');config['protected_roots'].append('/home/user/blikvm-p3-h3-exports')
config['cross_run'] += [str(q) for q in sorted((BASE/'sealed').iterdir())]
config['protected_files'] += [str(q) for q in (BASE/'sealed').rglob('*') if q.is_file()]
probe=LEGACY/'p3-context/a01-smoke/browser-msd/.h2-probe-1cd9f4afd2db4fa3aeed136f35858e42'
config['protected_files'].append(str(probe))
H['audit'](None,review/'after-seal-audit.json',config)
protected=F['protected'](config);publish(review/'protected-after.json',protected)
require(protected==read(run/'protected-before.json'),'protected input change')
processes=H['browser_idle']();publish(review/'browser-processes.json',processes)
for name,argv in {
 'controller-journal':['journalctl','-u','blikvm-p3-h3-chromium-001','--no-pager','-o','short-monotonic'],
 'bridge-journal-window':['journalctl','--since','2026-09-13 11:27:40','--until','2026-09-13 11:28:40','--no-pager','-o','json'],
 'bridge-kernel':['journalctl','-b','-k','--no-pager','-o','short-monotonic'],
}.items():
    p=subprocess.run(argv,capture_output=True,text=True)
    publish(review/(name+'.json'),{'returncode':p.returncode,'stdout':p.stdout,'stderr':p.stderr})
before=read(run/'before/target.json');after=read(run/'failure-preservation/target.json')
for k in ('hash_checks','boot_id','machine_id','host_public_keys','sd_cid'):require(before[k]==after[k],'target changed: '+k)
for inv in (before,after):runpy.run_path(str(BASE/'controller/preparation/assess.py'))['assess'](inv,read(BASE/'controller/preparation/p2-identity.json'))
require(len(before['hash_checks'])==10690,'expected hashes count drift')
require(not list((BASE/'active').iterdir()),'active output remains')
publish(review/'result.json',{'result':'FAILED_PRESERVED_PENDING_INDEPENDENT_REPLAY',
 'target_hashes_matched':10690,'boot_id':after['boot_id'],'protected_inputs_unchanged':True,
 'browser_processes':processes,'active_leaves':0,'qualification_credit':0,'reboots':0,
 'chromium_launches_attempted':1,'browser_smokes_completed':0,'retry_performed':False,
 'root_cause':'unassigned; Chromium exited SIGTRAP before first UI stage; controller subsequently required absent second launch audit'})
print('H3 failure preserved; post-seal audit passed; protected bytes/metadata unchanged; zero credit')
