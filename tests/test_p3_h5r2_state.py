import copy,json,runpy,unittest
from pathlib import Path
S=runpy.run_path(str(Path(__file__).resolve().parents[1]/'lab/p3-h5r2-state.py'))
class StateGate(unittest.TestCase):
 def setUp(self):
  self.inv={'boot_id':S['BOOT'],'commands':{'root':{'stdout':json.dumps({'filesystems':[{'source':'/dev/mmcblk0p1'}]})},'failed_units':{'stdout':''}},'hash_checks':{str(i):{'matches':True,'sha256':'a','expected':'a'} for i in range(10690)}}
  self.state={'boot_id':S['BOOT'],'gadgets':['blikvm_m5'],'functions':['hid.absolute','hid.keyboard','hid.relative','mass_storage.g4'],'luns':['lun.0'],'attrs':dict(S['ATTRS']),'api_returncode':0,'api':{'ok':True,'result':{'enabled':True,'online':True,'busy':False,'drive':{'connected':True,'rw':False,'cdrom':False,'image':{'name':'g4-storage.img','writable':False}},'storage':{'images':{'g4-storage.img':{}}}}}}
  self.host={'identity':{'ro':'1','size':'16384'},'bytes':8388608,'sha256':S['SHA']}
 def test_accepts_attached_complete_readonly_media(self):self.assertEqual(S['check'](self.inv,self.state,self.host)['result'],'ATTACHED_MSD_PREREQUISITE_PASS')
 def test_rejects_each_false_prerequisite_without_repair(self):
  cases=[('empty',lambda i,s,h:s['attrs'].update(file='')),('wrong_path',lambda i,s,h:s['attrs'].update(file='/usr/share/g4-storage.img')),('rw',lambda i,s,h:s['attrs'].update(ro='0')),('cdrom',lambda i,s,h:s['attrs'].update(cdrom='1')),('extra_lun',lambda i,s,h:s['luns'].append('lun.1')),('api_disconnected',lambda i,s,h:s['api']['result']['drive'].update(connected=False)),('host_absent',lambda i,s,h:h.update(bytes=0)),('host_rw',lambda i,s,h:h['identity'].update(ro='0')),('hash',lambda i,s,h:h.update(sha256='bad')),('boot',lambda i,s,h:i.update(boot_id='other')),('root',lambda i,s,h:i['commands']['root'].update(stdout=json.dumps({'filesystems':[{'source':'tmpfs'}]}))),('production',lambda i,s,h:i['hash_checks']['0'].update(matches=False)),('service',lambda i,s,h:i['commands']['failed_units'].update(stdout='kvmd.service'))]
  for name,mutate in cases:
   with self.subTest(name=name):
    i,s,h=copy.deepcopy((self.inv,self.state,self.host));mutate(i,s,h);before=copy.deepcopy((i,s,h))
    with self.assertRaises(AssertionError):S['check'](i,s,h)
    self.assertEqual((i,s,h),before)
if __name__=='__main__':unittest.main()
