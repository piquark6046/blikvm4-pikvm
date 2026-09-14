#!/usr/bin/env python3
"""Byte-bound H5R1 runtime inheritance plus independently replayed H5R2 sanity."""
import hashlib,json,runpy,shlex,sys,tarfile
from pathlib import Path
R=Path(__file__).resolve().parents[3]
sha=lambda b:hashlib.sha256(b).hexdigest()
def verify(new,expected):
 old=R/'out/p3-h5r1/functional-001-failed.tar.gz'
 assert sha(old.read_bytes())=='4fac32a311fd4649a1f2ff13003a3afee4be66b3c193b49bfd626e38d4968c48'
 result=runpy.run_path(str(Path(__file__).with_name('verify-h5r2.py')))['replay'](new,expected,'minimal-001')
 assert result['result']=='H5R2_MINIMAL_ACCEPTED'
 with tarfile.open(old) as a,tarfile.open(new) as b:
  read=lambda t,n:json.load(t.extractfile(n))
  c,d=read(a,'input/contract.json'),read(b,'input/contract.json')
  for k in ('launch_options','xvfb_arguments','chromium_sha256','playwright_sha256','playwright_version'):assert c[k]==d[k],k
  for name in ('/usr/bin/node','/usr/bin/Xvfb','/usr/bin/xvfb-run','/usr/bin/xauth'):assert c['executables'][name]['sha256']==d['executables'][name]['sha256']
  def files(m):return {k:v['sha256'] for k,v in m.items() if 'sha256' in v}
  assert files(c['runtime_manifest'])==files(d['runtime_manifest'])
  for name in ('p3-h5r1-netns.py','p3-h5r1-netns.cjs','p3-h3-boundary.py'):assert a.extractfile('input/'+name).read()==b.extractfile('input/'+name).read()
  def argv(t):
   line=read(t,'controller/minimal-001/result.json')['generated_argv_lines'][0]
   values=shlex.split(line.split('<launching> ',1)[1]);profiles=[v for v in values if v.startswith('--user-data-dir=')]
   assert len(profiles)==1 and profiles[0].startswith('--user-data-dir=/tmp/playwright_chromiumdev_profile-')
   return values[0],[v for v in values[1:] if not v.startswith('--user-data-dir=')]
  x,xf=argv(a);y,yf=argv(b);assert x==c['chromium'] and y==d['chromium'] and xf==yf
  assert c['uid']!=d['uid'] and d['home']=='/var/lib/blikvm-p3-h5r2/home'
  return dict(result='H5R2_RUNTIME_INHERITANCE_ACCEPTED',archive_sha256=expected,runtime_files=len(files(c['runtime_manifest'])),executables_identical=True,launch_options_identical=True,generated_stable_flags_identical=True,netns_implementation_identical=True,permission_worker_identical=True,minimal_launches_required=1,qualification_credit=0)
if __name__=='__main__':print(json.dumps(verify(Path(sys.argv[1]),sys.argv[2]),indent=2))
