#!/usr/bin/env python3
"""Exercise the candidate WebSocket dispatcher with live/revoked sessions."""
import argparse
import ast
import asyncio
import __future__
import json
from pathlib import Path
from types import SimpleNamespace

p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=Path('out/kvmd-hid/rootfs-rootfs'));a=p.parse_args()
source=a.root/'usr/lib/python3/dist-packages/kvmd/htserver.py'
tree=ast.parse(source.read_text())
original=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='HttpServer')
method=next(n for n in original.body if isinstance(n,ast.AsyncFunctionDef) and n.name=='_ws_loop')
klass=ast.ClassDef(name='HttpServer',bases=[],keywords=[],body=[method],decorator_list=[])
module=ast.fix_missing_locations(ast.Module(body=[klass],type_ignores=[]))
ns={'get_logger':lambda:SimpleNamespace(error=lambda *a:None),'WSMsgType':SimpleNamespace(TEXT=1,BINARY=2),
    'parse_ws_event':lambda text:(json.loads(text)['event_type'],json.loads(text)['event'])}
exec(compile(module,'<candidate dispatcher>','exec',flags=__future__.annotations.compiler_flag),ns)
async def check(binary,valid):
    calls=[]
    class Messages:
        def __aiter__(self):return self
        async def __anext__(self):
            if hasattr(self,'done'):raise StopAsyncIteration
            self.done=True
            return SimpleNamespace(type=2 if binary else 1,data=b'\x01\x01KeyA' if binary else '{"event_type":"key","event":{"key":"KeyA","state":true}}')
    async def handler(ws,data):calls.append(data)
    server=ns['HttpServer']()
    async def auth(ws):return valid
    server._check_ws_auth=auth
    server._HttpServer__ws_handlers={'key':handler}
    server._HttpServer__ws_bin_handlers={1:handler}
    await server._ws_loop(SimpleNamespace(wsr=Messages()))
    assert bool(calls)==valid,(binary,valid,calls)
async def main():
    for binary in (False,True):
        for valid in (False,True):await check(binary,valid)
asyncio.run(main())
print(json.dumps({'result':'passed','cases':4,'scope':'candidate JSON and binary per-message revocation dispatch; HIL still required'}))
