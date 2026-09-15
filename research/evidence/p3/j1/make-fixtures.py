#!/usr/bin/env python3
"""Create sanitized positive sequences and adversarial mutations from pinned records."""
import copy
import json
from pathlib import Path
import runpy
S=runpy.run_path(str(Path(__file__).with_name('study.py')))
C=runpy.run_path(str(S['ROOT']/'lab/p3-j1-classifier.py'))

def reduced(spec):
 _,rows,_=S['load'](spec);result=C['classify'](rows)
 keep={e['index'] for e in result['records']}
 keep.update(w['index'] for e in result['records'] for w in e['witnesses'])
 for i,r in enumerate(rows):
  m=r['MESSAGE']
  if m in C['STARTS'].values() or m==C['READY']:keep.add(i)
 for pattern in (C['LOGIN'],C['SUCCESS']):
  keep.add(next(i for i,r in enumerate(rows) if pattern.fullmatch(r['MESSAGE'])))
 out=[]
 for i in sorted(keep):
  r=rows[i];m=r['MESSAGE']
  # Remove auth identity and browser user-agent; preserve the complete semantic log grammar.
  m=m.replace("'qualifier'","'fixture-user'").replace('qualifier (token)','fixture-user (token)')
  if "user_agent='" in m:m=m.split("user_agent='")[0]+"user_agent='fixture-agent'"
  out.append({'MESSAGE':m,'PRIORITY':r['PRIORITY'],'_SYSTEMD_UNIT':r.get('_SYSTEMD_UNIT'),'_BOOT_ID':'a'*32,'__MONOTONIC_TIMESTAMP':r['__MONOTONIC_TIMESTAMP']})
 return out

a03=reduced(S['CORPUS'][4]);h5=reduced(S['CORPUS'][0])
fixtures=[]
def add(name,rows,expected=False):fixtures.append({'name':name,'expected_eligible':expected,'journal':rows})
add('positive-h5r2-boot-and-logout',h5,True);add('positive-a03-observed-startup-and-logout',a03,True)
ready=next(int(r['__MONOTONIC_TIMESTAMP']) for r in a03 if r['MESSAGE']==C['READY'])
def change(name,predicate,mutate):
 rows=copy.deepcopy(a03);i=next(i for i,r in enumerate(rows) if predicate(r));mutate(rows,i);add(name,rows)
def socket(r):return bool(C['SOCKET'].fullmatch(r['MESSAGE']))
def auth502(r):return bool(C['AUTH502'].fullmatch(r['MESSAGE']))
def reset(r):return bool(C['RESET'].fullmatch(r['MESSAGE']))
def move(rows,i):rows[i]['__MONOTONIC_TIMESTAMP']=str(ready+1);rows.sort(key=lambda r:int(r['__MONOTONIC_TIMESTAMP']))
change('A-socket-after-ready',socket,move);change('B-auth502-after-ready',auth502,move)
change('C-wrong-unit',socket,lambda r,i:r[i].update(_SYSTEMD_UNIT='kvmd.service'))
change('D-arbitrary-502',auth502,lambda r,i:r[i].update(MESSAGE='nginx ERROR arbitrary upstream 502'))
for name,pattern in [('E-no-logout',C['LOGOUT']),('F-no-reauth',C['LOGIN']),('G-no-removed-socket',C['REMOVED'])]:
 rows=[copy.deepcopy(r) for r in a03 if not pattern.fullmatch(r['MESSAGE'])];add(name,rows)
change('H-unknown-startup-error',socket,lambda r,i:r[i].update(MESSAGE='unknown.component ERROR unexpected startup fault'))
rows=copy.deepcopy(a03)
for n in range(3):
 for r in a03:
  if socket(r) or auth502(r):
   e=copy.deepcopy(r);e['__MONOTONIC_TIMESTAMP']=str(ready+1+n);rows.append(e)
rows.sort(key=lambda r:int(r['__MONOTONIC_TIMESTAMP']));add('I-repeated-after-readiness',rows)
change('J-reordered-causal-sequence',socket,lambda r,i:r.insert(0,r.pop(i)))
add('missing-readiness',[copy.deepcopy(r) for r in a03 if r['MESSAGE']!=C['READY']])
change('wrong-upstream',socket,lambda r,i:r[i].update(MESSAGE=r[i]['MESSAGE'].replace('kvmd.sock','other.sock')))
change('wrong-reset-path',reset,lambda r,i:r[i].update(MESSAGE=r[i]['MESSAGE'].replace('/api/ws','/other/ws')))
change('mixed-boot',socket,lambda r,i:r[i].update(_BOOT_ID='b'*32))
change('unknown-high-priority',socket,lambda r,i:r[i].update(MESSAGE='unexplained low-case failure',PRIORITY='3'))
rows=copy.deepcopy(a03);e=copy.deepcopy(next(r for r in rows if r['MESSAGE']==C['READY']));rows.append(e);rows.sort(key=lambda r:int(r['__MONOTONIC_TIMESTAMP']));add('duplicate-readiness',rows)
rows=copy.deepcopy(a03)
for r in rows:r['__MONOTONIC_TIMESTAMP']=str(int(r['__MONOTONIC_TIMESTAMP'])+900000000)
add('positive-time-translation',rows,True)
# Reordering timestamps while retaining valid journal order must also fail.
rows=copy.deepcopy(a03)
next(r for r in rows if r['MESSAGE']==C['READY'])['__MONOTONIC_TIMESTAMP']=str(min(int(r['__MONOTONIC_TIMESTAMP']) for r in rows)+1)
rows.sort(key=lambda r:int(r['__MONOTONIC_TIMESTAMP']));add('J-sorted-but-invalid-readiness-sequence',rows)
rows=copy.deepcopy(h5)
end=int(next(r for r in rows if r['MESSAGE']==C['READY'])['__MONOTONIC_TIMESTAMP'])
next(r for r in rows if r['MESSAGE']==C['STARTS']['kvmd.service'])['__MONOTONIC_TIMESTAMP']=str(end+1)
rows.sort(key=lambda r:int(r['__MONOTONIC_TIMESTAMP']));add('J-kvmd-start-after-readiness',rows)
rows=copy.deepcopy(h5)
end=max(int(r['__MONOTONIC_TIMESTAMP']) for r in rows)
next(r for r in rows if r['MESSAGE']==C['STARTS']['nginx.service'])['__MONOTONIC_TIMESTAMP']=str(end+1)
rows.sort(key=lambda r:int(r['__MONOTONIC_TIMESTAMP']));add('J-nginx-start-after-reset',rows)
# Offline fixtures use the actual accepted P2 startup witnesses from A01 preboot.
_,p2,_=S['load'](next(x for x in S['CORPUS'] if x[0]=='p2-accepted-a01-preboot'))
wanted=set(C['OFFLINE']) | {('init.scope',m) for m in C['STARTS'].values()} | {('kvmd.service',C['READY'])}
selected=[];seen=set()
for r in p2:
 key=(r.get('_SYSTEMD_UNIT'),r['MESSAGE'])
 label=key if key in wanted else ('first-login' if C['LOGIN'].fullmatch(r['MESSAGE']) else 'first-success' if C['SUCCESS'].fullmatch(r['MESSAGE']) else None)
 if label is not None and label not in seen:
  seen.add(label);e={k:r[k] for k in ('MESSAGE','PRIORITY','_SYSTEMD_UNIT','_BOOT_ID','__MONOTONIC_TIMESTAMP')};e['_BOOT_ID']='a'*32
  e['MESSAGE']=e['MESSAGE'].replace("'qualifier'","'fixture-user'").replace('qualifier (token)','fixture-user (token)')
  if "user_agent='" in e['MESSAGE']:e['MESSAGE']=e['MESSAGE'].split("user_agent='")[0]+"user_agent='fixture-agent'"
  selected.append(e)
fixtures.append({'name':'positive-inherited-offline-startup','expected_eligible':True,'offline':True,'journal':selected})
for label,missing in [('offline-missing-carrier',C['OFFLINE'][4]),('offline-missing-ssh',C['OFFLINE'][3])]:
 fixtures.append({'name':label,'expected_eligible':False,'offline':True,'journal':[r for r in selected if (r['_SYSTEMD_UNIT'],r['MESSAGE'])!=missing]})
rows=copy.deepcopy(selected)
next(r for r in rows if r['MESSAGE']==C['OFFLINE'][1][1])['_SYSTEMD_UNIT']='nginx.service'
fixtures.append({'name':'offline-wrong-unit','expected_eligible':False,'offline':True,'journal':rows})
fixtures.append({'name':'offline-not-authorized-connected-mode','expected_eligible':False,'offline':False,'journal':selected})
Path(__file__).with_name('fixtures.json').write_text(json.dumps(fixtures,indent=2)+'\n')
print(len(fixtures))
