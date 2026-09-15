#!/usr/bin/env python3
"""Build-VM-only independent corpus/fixture replay. Writes only new private output."""
import argparse
import hashlib
import json
from pathlib import Path
import runpy

HERE=Path(__file__).resolve().parent
S=runpy.run_path(str(HERE/'study.py'))
C=runpy.run_path(str(S['ROOT']/'lab/p3-j1-classifier.py'))
REFERENCE=runpy.run_path(str(HERE/'reference.py'))['verify']


def compare(rows,offline=False):
    candidate=C['classify'](rows,offline=offline);eligible,independent=REFERENCE(rows,offline=offline)
    if (candidate['result']=='JOURNAL_ELIGIBLE')!=eligible:raise ValueError('independent decision mismatch')
    actual=[(r['index'],r['classification'],[w['index'] for w in r['witnesses']]) for r in candidate['records']]
    if actual!=independent:raise ValueError('independent per-record/witness mismatch')
    return candidate


def verify(out):
    out.mkdir(mode=0o700,parents=True,exist_ok=False)
    corpus=[]
    for spec in S['CORPUS']:
        inv,rows,meta=S['load'](spec)
        if meta['format']=='journal_json':
            result=compare(rows,offline=spec[0]=='p2-accepted-a01-preboot')
            if spec[0]=='p2-accepted-a01-preboot':
                if result['result']!='REJECTED':raise ValueError('P2 intentional restarts/invalid-auth accepted as P3')
                with (out/(spec[0]+'.json')).open('x') as f:json.dump({**meta,**result},f,indent=2)
                corpus.append({**meta,'classifier_result':'REJECTED','reason':'historical intentional auth/restart tests outside P3 semantics','historical_status_unchanged':True})
                continue
            if result['result']!='JOURNAL_ELIGIBLE':raise ValueError((spec[0],result['reason']))
            expected={'h5r2-functional-001':(0,2),'h5r2-functional-002':(0,3),'h5r2-functional-003':(0,6),'a01-cycle-001':(6,0),'a03-cycle-001':(6,1)}[spec[0]]
            counts=tuple(sum(r['classification']==kind for r in result['records']) for kind in ('STARTUP_CAUSAL','LOGOUT_RESET_CAUSAL'))
            if counts!=expected:raise ValueError(('candidate count',spec[0],counts))
            # This separate gate cannot promote attempt 01's incomplete core smoke.
            if spec[0]=='a01-cycle-001':
                try:C['require_qualification'](rows,https_passed=True,auth_passed=True,core_passed=False,generations_unchanged=True)
                except ValueError:pass
                else:raise ValueError('incomplete core gate accepted')
        else:
            if C['classify'](rows)['result']!='REJECTED' or REFERENCE(rows)[0]:raise ValueError('text without trusted metadata accepted')
            result={'result':'REJECTED','reason':'text journal lacks trusted unit/priority metadata; observational only','records':[dict(r,classification='REJECTED_MISSING_TRUSTED_METADATA',witnesses=[],reason='not comparable for P3 qualification') for r in S['timeline'](rows) if r['error_candidate']]}
            counts=None
        with (out/(spec[0]+'.json')).open('x') as f:json.dump({**meta,**result},f,indent=2);f.write('\n')
        corpus.append({**meta,'classifier_result':result['result'],'startup_reset_counts':counts,'historical_status_unchanged':True})
    fixtures=json.loads((HERE/'fixtures.json').read_text());results=[]
    for f in fixtures:
        r=compare(f['journal'],offline=f.get('offline',False))
        if (r['result']=='JOURNAL_ELIGIBLE')!=f['expected_eligible']:raise ValueError(('fixture result',f['name'],r))
        results.append({'name':f['name'],'expected_eligible':f['expected_eligible'],'result':r['result']})
    summary={'result':'P3_J1_CLASSIFIER_REPLAY_PASS','corpus':corpus,'fixtures':results,'independent_per_record_and_witness_agreement':True,'a03_status':'PERMANENTLY_FAILED','a03_accepted_cycles':0,'qualification_credit':0,'p3':'UNACCEPTED','target_contacted':False,'source_sha256':{str(p.relative_to(S['ROOT'])):hashlib.sha256(p.read_bytes()).hexdigest() for p in [S['ROOT']/'lab/p3-j1-classifier.py',HERE/'study.py',HERE/'reference.py',HERE/'verify.py',HERE/'semantics.md',HERE/'fixtures.json',HERE/'functional.py',HERE/'make-fixtures.py']}}
    with (out/'summary.json').open('x') as f:json.dump(summary,f,indent=2);f.write('\n')
    return summary

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('output',type=Path);a=p.parse_args();print(json.dumps(verify(a.output),indent=2))
