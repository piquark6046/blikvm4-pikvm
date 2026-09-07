#!/usr/bin/env python3
"""Exercise installed upstream handler bodies and read-only guard without hardware."""
import argparse
import ast
import asyncio
from pathlib import Path
from types import SimpleNamespace

p=argparse.ArgumentParser();p.add_argument('--source',type=Path,default=Path('out/kvmd-msd/patched'));a=p.parse_args()
registered=[]
def expose(method,route):
    registered.append((method,route))
    return lambda f:f
source=ast.parse((a.source/'kvmd/apps/kvmd/api/msd.py').read_text())
source.body=[n for n in source.body if isinstance(n,ast.ClassDef)]
ns={'Request':object,'Response':object,'BaseMsd':object,'MsdOperationError':RuntimeError,
    'exposed_http':expose,'make_json_response':lambda x=None:x,'valid_bool':lambda x:x=='true'}
exec(compile(source,'api/msd.py','exec'),ns)
assert registered==[('GET','/msd'),('POST','/msd/set_params'),('POST','/msd/set_connected')],registered
class Backend:
    async def set_connected(self,v):raise AssertionError('backend must not be called')
    async def set_params(self,**kwargs):raise AssertionError('backend must not be called')
api=ns['MsdApi'](Backend())
class Duplicate(dict):
    def __len__(self):return super().__len__()+1
for handler,queries in [
    (api._MsdApi__set_params_handler,[{'path':'/etc/passwd'},Duplicate(rw='false')]),
    (api._MsdApi__set_connected_handler,[{}, {'connected':'true','rw':'true'},Duplicate(connected='true')])]:
    for query in queries:
        try:asyncio.run(handler(SimpleNamespace(query=query)))
        except RuntimeError:pass
        else:raise AssertionError('malformed query accepted')
plugin=ast.parse((a.source/'kvmd/plugins/msd/otg/__init__.py').read_text())
cls=next(n for n in plugin.body if isinstance(n,ast.ClassDef) and n.name=='Plugin')
fn=next(n for n in cls.body if isinstance(n,ast.AsyncFunctionDef) and n.name=='set_params')
fn.decorator_list=[]
ns={'Any':object,'MsdOperationError':RuntimeError}
exec(compile(ast.Module(body=[fn],type_ignores=[]),'otg/set_params.py','exec'),ns)
for kwargs in ({'rw':True},{'cdrom':True},{'name':'g4-storage.img','rw':True}):
    try:asyncio.run(ns['set_params'](SimpleNamespace(__readonly=True),**kwargs))
    except RuntimeError:pass
    else:raise AssertionError('read-only guard did not reject')
print('PASS: exactly three routes; malformed/duplicate queries and RW/CD-ROM rejected before mutation')
