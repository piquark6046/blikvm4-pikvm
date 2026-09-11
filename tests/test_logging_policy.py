"""Regression for actual systemd drop-in precedence and immutable policy values."""
import configparser,pathlib,subprocess,tempfile,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
class LoggingPolicyTests(unittest.TestCase):
 def test_effective_policy_overrides_ubuntu_syslog_dropin(self):
  with tempfile.TemporaryDirectory() as d:
   root=pathlib.Path(d)
   for n in ['etc/systemd/journald.conf.d','usr/lib/systemd/journald.conf.d']:(root/n).mkdir(parents=True)
   (root/'etc/systemd/journald.conf').write_text('[Journal]\nStorage=persistent\n')
   (root/'usr/lib/systemd/journald.conf.d/syslog.conf').write_text('[Journal]\nForwardToSyslog=yes\n')
   policy=(ROOT/'build/logging/zz-blikvm-bounded.conf').read_text()
   (root/'etc/systemd/journald.conf.d/zz-blikvm-bounded.conf').write_text(policy)
   output=subprocess.check_output(['systemd-analyze','--root='+d,'cat-config','systemd/journald.conf'],text=True)
   c=configparser.ConfigParser(strict=False);c.read_string(output)
   for k,v in {'Storage':'volatile','RuntimeMaxUse':'16M','RuntimeMaxFileSize':'4M','Compress':'yes','ForwardToSyslog':'no'}.items():self.assertEqual(c['Journal'][k],v)
 def test_retention_result_cannot_satisfy_full_soak_gate(self):
  import runpy
  retention=runpy.run_path(str(ROOT/'lab/verify-logging-retention.py'))['duration_gate']
  full=runpy.run_path(str(ROOT/'lab/verify-core-soak.py'))['duration_gate']
  result={'qualification':False,'diagnostic':'M8-F2','required_seconds':7200,'result':'completed_pending_independent_review','start_monotonic':0,'end_monotonic':7211}
  self.assertTrue(retention(result));self.assertFalse(full(result))
  result['end_monotonic']=7199
  self.assertFalse(retention(result))
 @unittest.skipUnless((ROOT/"out/m8f2/build1/rootfs.tar.gz").exists(), "requires logging candidate build")
 def test_nginx_policy_changes_only_logging_directives(self):
  import tarfile
  with tarfile.open(ROOT/'out/m8f2/build1/rootfs.tar.gz') as t:s=t.extractfile('./etc/kvmd/nginx/nginx.conf').read().decode()
  expected=(ROOT/'build/kvmd-lan/nginx.conf').read_text().replace('error_log /var/log/nginx/error.log warn;','error_log stderr warn;').replace('access_log /var/log/nginx/access.log combined;','access_log off;')
  self.assertEqual(s,expected)
if __name__=='__main__':unittest.main()
