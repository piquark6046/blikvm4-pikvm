#!/usr/bin/env python3
"""Add per-Chromium-launch syscall gate and frozen protocol validation."""
import os
from pathlib import Path
import runpy
import shutil

H=runpy.run_path(str(Path(__file__).with_name('p3-h3-boundary.py')))
BASE=H['BASE'];publish=H['publish'];require=H['require']
require(os.geteuid()==0,'root required');H['browser_idle']();os.umask(0o077)
require(H['read_json'](BASE/'controller/permission-vm-replay.json')['result']=='H3_PERMISSION_ONLY_PASS','independent permission replay required')
require(not (BASE/'controller/FAILED.json').exists(),'H3 failed; no retry')
ctx=BASE/'input/context';changes={}
for name in ('p3-h3-boundary.py','p3-h3-protocol.json'):
    shutil.copyfile(Path(__file__).with_name(name),ctx/'lab'/name);(ctx/'lab'/name).chmod(0o644)
for label in ('msd','hid'):
    p=ctx/'lab'/(label+'-browser-hil.py');before=H['digest'](p);text=p.read_text()
    setup="PROTOCOL=P3['read_json'](Path(__file__).with_name('p3-h3-protocol.json'))['"+label+"']\n"
    text=text.replace("LEAF=Path(os.environ['P3_BROWSER_LEAF'])\n","LEAF=Path(os.environ['P3_BROWSER_LEAF'])\n"+setup)
    if label=='msd':
        old="value=P3['read_json'](stage);check={'result':'failed'}"
        new="value=P3['read_json'](stage);P3['require'](stage.name == f'{len(seen):03d}.ready' and value == PROTOCOL[len(seen)-1], 'untrusted MSD stage');check={'result':'failed'}"
    else:
        old="spec=P3['read_json'](ready);before="
        new="spec=P3['read_json'](ready);P3['require'](1 <= index <= len(PROTOCOL) and spec == PROTOCOL[index-1], 'untrusted HID stage');before="
    require(text.count(old)==1,'protocol patch context drift');text=text.replace(old,new)
    p.write_text(text);changes[p.name]={'before':before,'after':H['digest'](p)}
    p=ctx/'lab'/(label+'-browser.mjs');before=H['digest'](p);text=p.read_text()
    # execFileSync runs the exact global auditor with the browser's real identity.
    if label=='msd':text="import {execFileSync} from 'node:child_process';\n"+text.removeprefix('#!/usr/bin/env node\n')
    guard="""
let h3LaunchNumber=0;
function h3LaunchGate(){
 const destination=path.join(out,'launch-audit-'+String(++h3LaunchNumber).padStart(3,'0')+'.json');
 let raw;
 try {raw=execFileSync('/usr/bin/python3',[path.resolve('lab/p3-h3-boundary.py'),'--worker'],{input:fs.readFileSync(process.env.P3_LAUNCH_REQUIREMENTS),encoding:'utf8',maxBuffer:64*1024*1024});}
 catch(e){if(e.stdout)fs.writeFileSync(destination,e.stdout);throw e;}
 fs.writeFileSync(destination,raw);
 const a=JSON.parse(raw);assert.equal(a.uid,995);assert.equal(a.gid,983);assert.deepEqual(a.groups,[983]);
 assert(a.operations.length>0 && a.operations.every(o=>o.passed));
}
"""
    text=text.replace('try {\n browser=await chromium.launch',guard+'\ntry {\n browser=await chromium.launch',1)
    require(text.count('await chromium.launch')==(2 if label=='msd' else 1),'unexpected launch count')
    text=text.replace('browser=await chromium.launch','h3LaunchGate();browser=await chromium.launch')
    p.write_text(text);changes[p.name]={'before':before,'after':H['digest'](p)}
publish(BASE/'controller/browser-installation.json',{'changes':changes,'input_manifest':H['manifest'](BASE/'input'),
        'target_contacted':False,'qualification_credit':0})
print('Per-launch gate installed; target and Chromium not contacted')
