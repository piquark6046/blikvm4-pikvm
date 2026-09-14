import copy
import json
import os
from pathlib import Path
import runpy
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
N = runpy.run_path(str(ROOT/'lab/p3-h5r1-netns.py'))


def fixture():
    r={'netns':'net:[2]', 'host_netns':'net:[1]', 'sockets':[], 'raw':{}}
    values={'lo_up':'', 'link':'[{"ifname":"lo"}]',
            'addr':'[{"ifname":"lo","addr_info":[{"local":"127.0.0.1"},{"local":"::1"}]}]',
            'route':'[]', 'route_all':'[{"dev":"lo"}]', 'route6':'[{"dev":"lo"}]', 'target_route':''}
    for k,v in values.items():
        r['raw'][k]={'returncode':2 if k=='target_route' else 0, 'stdout':v,
                     'stderr':'RTNETLINK answers: Network is unreachable' if k=='target_route' else ''}
    return r


class NetnsTests(unittest.TestCase):
    def test_sysfs_never_authoritative(self):
        for sysfs in (['lo'], ['enp1s0','lo','wlo1'], [], {'error':'EACCES'}):
            r=fixture();r['sysfs_interfaces_observed']=sysfs
            N['validate'](r)

    def test_reject_external_state_and_failed_commands(self):
        for key, val in [('link','[{"ifname":"lo"},{"ifname":"eth0"}]'),
                         ('addr','[{"ifname":"lo","addr_info":[{"local":"192.168.88.2"}]}]'),
                         ('route','[{"dev":"eth0","dst":"default"}]'),
                         ('route6','[{"dev":"eth0"}]')]:
            r=fixture();r['raw'][key]['stdout']=val
            with self.assertRaises(RuntimeError):N['validate'](r)
        for field,value in [('netns','net:[1]'),('sockets',[{'fd':'0','target':'socket:[12]'}])]:
            r=fixture();r[field]=value
            with self.assertRaises(RuntimeError):N['validate'](r)
        for key in fixture()['raw']:
            r=fixture();r['raw'][key]['returncode']=0 if key=='target_route' else 1
            with self.assertRaises(RuntimeError):N['validate'](r)

    def test_node_sysfs_diagnostic_independence(self):
        node=os.environ.get('H5R1_TEST_NODE') or shutil.which('node')
        self.assertIsNotNone(node)
        script="""
const n=require(process.argv[1]);
const r={netns:'net:[2]',uid:3,gid:4,groups:[4],sockets:[],interfaces:{lo:[{internal:true,address:'127.0.0.1'}]},raw:{
link:{status:0,stdout:'[{"ifname":"lo"}]'},route:{status:0,stdout:'[]'},route6:{status:0,stdout:'[]'}}};
const e={host_netns:'net:[1]',netns:r.netns,uid:3,gid:4,groups:[4]};
for(const s of [['lo'],['enp1s0','lo','wlo1'],[],{error:'EACCES'}]){r.sysfs_interfaces_observed=s;n.validate(r,e);}
r.interfaces.eth0=[];require('node:assert').throws(()=>n.validate(r,e));
"""
        subprocess.run([node,'-e',script,str(ROOT/'lab/p3-h5r1-netns.cjs')],check=True,capture_output=True)

    @unittest.skipUnless(os.environ.get('H5R1_PRIVILEGED_NETNS_TEST')=='1',
                         'explicit privileged VM regression required separately')
    def test_real_netns_inherited_sysfs_and_uid_drop(self):
        self.assertEqual(os.geteuid(),0)
        node=os.environ.get('H5R1_TEST_NODE') or shutil.which('node') or '/usr/bin/node'
        script="""
import json,os,runpy,subprocess,sys
n=runpy.run_path(sys.argv[1]);r=n['observe'](sys.argv[3]);n['validate'](r)
r.update(uid=65534,gid=65534,groups=[65534]);print(json.dumps({'before':r}),flush=True)
os.setgroups([65534]);os.setgid(65534);os.setuid(65534)
os.execve(sys.argv[4],[sys.argv[4],sys.argv[2]],{'H5R1_NETNS_EXPECTED':json.dumps(r),'PATH':'/usr/bin:/bin'})
"""
        # Use public copies so VM home traversal does not influence the netns test.
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);root.chmod(0o755)
            shutil.copyfile(node,root/'node');(root/'node').chmod(0o755);node=str(root/'node')
            for name in ('p3-h5r1-netns.py','p3-h5r1-netns.cjs'):
                shutil.copyfile(ROOT/'lab'/name,root/name);(root/name).chmod(0o644)
            p=subprocess.run(['/usr/bin/unshare','--net','/usr/bin/python3','-c',script,
                str(root/'p3-h5r1-netns.py'),str(root/'p3-h5r1-netns.cjs'),os.readlink('/proc/self/ns/net'),node],
                stdin=subprocess.DEVNULL,capture_output=True,text=True,close_fds=True)
            self.assertEqual(p.returncode,0,p.stdout+p.stderr)
            before,after=map(json.loads,p.stdout.splitlines())
            self.assertEqual(before['before']['netns'],after['netns'])
            self.assertEqual(list(after['interfaces']),['lo'])
            self.assertIn('sysfs_interfaces_observed',after)
            print('H5R1_VM_NETNS_RAW='+p.stdout)


if __name__=='__main__':unittest.main()

class ControllerGates(unittest.TestCase):
    def test_copy_identity_excludes_only_allocation_metadata(self):
        h=runpy.run_path(str(ROOT/'lab/p3-h5r1.py'))
        a={'f':{'type':32768,'sha256':'a','mode':493,'uid':0,'gid':0,'size':12,'dev':1,'ino':2,'ctime_ns':3}}
        b=copy.deepcopy(a);b['f'].update(dev=9,ino=10,ctime_ns=11)
        self.assertEqual(h['runtime_identity'](a),h['runtime_identity'](b))
        b['f']['mode']=420
        self.assertNotEqual(h['runtime_identity'](a),h['runtime_identity'](b))

    def test_replay_must_match_exact_archive(self):
        from unittest.mock import patch
        h=runpy.run_path(str(ROOT/'lab/p3-h5r1.py'));fn=h['prior_replay']
        with patch.dict(fn.__globals__,read=lambda p: {'seal':{'sha256':'a'}} if p.name=='result.json' else
                        {'result':'H5R1_MINIMAL_ACCEPTED','name':'minimal-001','leaf_archive_sha256':'b'}):
            with self.assertRaisesRegex(RuntimeError,'archive mismatch'):fn('minimal-001')

    def test_replay_rejects_traversal_and_links(self):
        import io,tarfile
        h=runpy.run_path(str(ROOT/'research/evidence/p3/verify-h5r1.py'))
        for name,kind in [('../escape',tarfile.REGTYPE),('link',tarfile.SYMTYPE)]:
            stream=io.BytesIO()
            with tarfile.open(fileobj=stream,mode='w') as t:
                m=tarfile.TarInfo(name);m.type=kind;t.addfile(m)
            stream.seek(0)
            with tarfile.open(fileobj=stream) as t:
                with self.assertRaises(RuntimeError):h['entries'](t)
