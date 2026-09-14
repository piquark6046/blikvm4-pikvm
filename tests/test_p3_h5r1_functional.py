import ast
import os
from pathlib import Path
from types import SimpleNamespace
import unittest

ROOT=Path(__file__).resolve().parents[1]


class FunctionalLaunchTests(unittest.TestCase):
    def test_host_environment_cannot_leak_into_browser(self):
        tree=ast.parse((ROOT/'lab/p3-h5r1-functional.py').read_text())
        function=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='browser')
        calls=[]
        env={'P3_CONTROL':'/acks','P3_LAUNCH_REQUIREMENTS':'/requirements','P3_BROWSER_LEAF':'/leaf',
             'TMPDIR':'/bad','XDG_RUNTIME_DIR':'/bad','SECRET_HOST_VARIABLE':'never-pass'}
        fake=SimpleNamespace(environ=env,readlink=lambda p:'net:[123]',
            setgroups=lambda x:calls.append(('groups',x)),setgid=lambda x:calls.append(('gid',x)),
            setuid=lambda x:calls.append(('uid',x)),chdir=lambda x:calls.append(('cwd',x)),
            umask=lambda x:calls.append(('umask',x)),execve=lambda *a:calls.append(('exec',a)))
        c={'uid':993,'gid':981,'groups':[981],'cwd':'/input','environment':{'HOME':'/home','PATH':'/usr/bin:/bin','DEBUG':'pw:browser*'},
           'xvfb_arguments':['-a','-s','-screen 0 1600x1200x24 -nolisten tcp']}
        def require(ok,why):
            if not ok:raise RuntimeError(why)
        scope={'read':lambda p:c,'BASE':Path('/base'),'CTX':Path('/ctx'),'os':fake,'require':require}
        exec(compile(ast.Module(body=[function],type_ignores=[]),'functional-launch','exec'),scope)
        scope['browser']('msd')
        self.assertEqual(calls[:4],[('groups',[981]),('gid',981),('uid',993),('cwd','/input')])
        executable,args,actual=calls[-1][1]
        self.assertEqual(executable,'/usr/bin/xvfb-run')
        self.assertEqual(args[1:4],c['xvfb_arguments'])
        self.assertEqual(args[-2:],['/ctx/private','/leaf'])
        for key in ('TMPDIR','XDG_RUNTIME_DIR','SECRET_HOST_VARIABLE'):self.assertNotIn(key,actual)
        self.assertEqual(actual['HOME'],'/home');self.assertEqual(actual['DEBUG'],'pw:browser*')
        self.assertEqual(actual['H5R1_HOST_NETNS'],'net:[123]')
        with self.assertRaises(RuntimeError):scope['browser']('unexpected')

    def test_frozen_hid_protocol_has_no_service_repair(self):
        import json
        protocol=json.loads((ROOT/'lab/p3-h3-protocol.json').read_text())
        self.assertTrue(all(x.get('kind')!='restart' and 'service' not in x for x in protocol['hid']))
        for label in ('msd','hid'):
            browser=(ROOT/f'lab/p3-h5r1-{label}-browser.mjs').read_text()
            self.assertNotIn('kvmd-restart-cleanup',browser)
            self.assertEqual(browser.count('launchGate(out);browser=await chromium.launch({headless:false})'),2 if label=='msd' else 1)
            self.assertNotIn('ignoreHTTPSErrors:true',browser)
