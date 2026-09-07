#!/usr/bin/env python3
"""Check candidate against frozen M8-D files and exact report encodings."""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import struct
p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=Path('out/kvmd-msd/rootfs-rootfs'));a=p.parse_args()
r=a.root;base=Path('out/kvmd-hid/rootfs-rootfs');lib=Path('usr/lib/python3/dist-packages/kvmd')
# Every inherited file is frozen unless explicitly reviewed here.
allowed={str(lib/x) for x in ('apps/kvmd/__init__.py','apps/kvmd/server.py','apps/kvmd/api/msd.py',
          'plugins/msd/otg/__init__.py','plugins/msd/otg/drive.py')}
allowed.update(('usr/share/kvmd/web/share/js/kvm/msd.js','usr/share/kvmd/web/kvm/index.html'))
checked=[]
for prefix in ('usr/lib/python3/dist-packages/kvmd','usr/share/kvmd/web','etc/kvmd',
               'usr/lib/systemd/system/kvmd.service','usr/lib/systemd/system/kvmd.service.d',
               'etc/systemd/system/nginx.service','etc/systemd/system/nginx.service.d',
               'etc/systemd/system/blikvm-access.service','usr/bin/ustreamer',
               'usr/lib/udev/rules.d/99-blikvm-video.rules'):
    path=base/prefix
    for f in ([path] if path.is_file() else path.rglob('*')):
        if not f.is_file() or '__pycache__' in f.parts:continue
        relative=str(f.relative_to(base))
        if relative in allowed:continue
        assert (r/relative).read_bytes()==f.read_bytes(),relative
        checked.append(relative)
for helper in ('hid-keyboard','hid-absolute-mouse','hid-relative-mouse','gadget-storage'):
    path='usr/bin/'+helper
    assert (r/path).read_bytes()==(base/path).read_bytes(),path
for name in ('hid-absolute-mouse.report','hid-relative-mouse.report','g4-storage.img','g4-storage.sha256'):
    path='usr/share/'+name
    assert (r/path).read_bytes()==(base/path).read_bytes(),path
source=(r/lib/'plugins/hid/otg/events.py').read_text()
tree=ast.parse(source)
fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='make_mouse_report')
ns={'struct':struct};exec(compile(ast.Module(body=[fn],type_ignores=[]),'<candidate serializer>','exec'),ns)
make=ns['make_mouse_report']
assert make(True,1,256,512,None,0)==bytes.fromhex('0100010002')
assert make(True,0,32767,32767,None,0)==bytes.fromhex('00ff7fff7f')
assert make(False,1,-127,127,None,0)==bytes.fromhex('01817f')
assert make(False,0,0,0,None,0)==b'\0\0\0'
assert make(True,24,0,0,127,127)==b'\0'*5
for f in (r/lib).rglob('*.py'):ast.parse(f.read_text(),str(f))
print(json.dumps({'result':'passed','frozen_files':checked,'serializer_cases':5},indent=2))
