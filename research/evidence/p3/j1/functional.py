#!/usr/bin/env python3
"""Reuse pinned functional gates with a new causal journal section, offline only."""
import hashlib
import json
from pathlib import Path
import runpy
import tarfile

ROOT=Path(__file__).resolve().parents[4]
FROZEN=ROOT/'research/evidence/p3/verify-h5r2-functional.py'
FROZEN_SHA='32656afa330544eb64c0003d949ffdaf4ff4b4c48364b521561580d1f99d3ce8'


def replay(archive,digest,name,*,cycle_boot=None,offline=False):
    if not __debug__:raise ValueError('frozen assertions must be enabled')
    raw=FROZEN.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=FROZEN_SHA:raise ValueError('frozen H5R2 verifier changed')
    code=raw.decode()
    start=code.index('        errors=[]\n');end=code.index('        # Bounded journals',start)
    code=code[:start]+'''        causal = causal_gate(journal, https_passed=True, auth_passed=True,
            core_passed=True, generations_unchanged=True, offline=offline_mode)
        logout_resets = [e for e in causal['records'] if e['classification']=='LOGOUT_RESET_CAUSAL']
'''+code[end:]
    if cycle_boot is not None:
        replacements={
          "first=read(root/'controller/target-continuity/before-first-functional/target.json')":"first=read(root/'controller'/name/'startup/target.json')",
          "assert before['boot_id']=='1c8365c7-90bf-46fb-8db4-5ec06a745a6a'":"assert before['boot_id']==cycle_boot",
          "j(gate+'target-state.json'),j(gate+'host.json'))":"j(gate+'target-state.json'),j(gate+'host.json'),expected_boot=cycle_boot)",
        }
        for old,new in replacements.items():
            if code.count(old)!=1:raise ValueError('inherited gate binding changed')
            code=code.replace(old,new)
    classifier=runpy.run_path(str(ROOT/'lab/p3-j1-classifier.py'))
    g={'__file__':str(FROZEN),'__name__':'p3_j1_offline_functional','cycle_boot':cycle_boot,'offline_mode':offline,'causal_gate':classifier['require_qualification']}
    exec(compile(code,str(FROZEN)+'+J1','exec'),g)
    result=g['replay'](archive,digest,name)
    result.update(result='P3_J1_FUNCTIONAL_PREREQUISITES_REPLAYED',qualification_credit=0,accepted_cycles=0,historical_status_unchanged=True)
    return result


if __name__=='__main__':
    import sys
    studies=runpy.run_path(str(Path(__file__).with_name('study.py')))
    results=[]
    for spec in studies['CORPUS']:
        if not spec[0].startswith(('h5r2-','a03-')):continue
        inv,_,_=studies['load'](spec)
        name=spec[3].split('/')[1]
        results.append(replay(ROOT/spec[1],spec[2],name,cycle_boot=inv['boot_id'] if spec[0].startswith('a03-') else None))
    print(json.dumps({'result':'P3_J1_FUNCTIONAL_CORPUS_PASS','qualification_credit':0,'a03_status':'PERMANENTLY_FAILED','replays':results},indent=2))
