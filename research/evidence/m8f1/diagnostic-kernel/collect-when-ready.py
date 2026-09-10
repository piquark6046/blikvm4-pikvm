"""VM-side SFTP collection and independent replay after bridge finalization."""
import hashlib,json,os,subprocess,tarfile,time
from pathlib import Path
ROOT=Path('/home/user/repos/blikvm4-pikvm');os.chdir(ROOT)
output=ROOT/'out/m8f1/review';output.mkdir(mode=0o700,exist_ok=False)
base='/home/user/blikvm-msd/m8f1/'
ssh=['sftp','-b','-','-i','/tmp/m8f1-bridge-key','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-o','UserKnownHostsFile='+str(ROOT/'out/kvmd-msd/bridge-known-hosts'),'user@172.16.10.118']
def transfer(names):
    return subprocess.run(ssh,input=''.join('get '+base+n+' '+str(output/n)+'\n' for n in names),text=True,capture_output=True,timeout=300)
deadline=time.monotonic()+14*3600
while time.monotonic()<deadline:
    r=transfer(['observation01-archive.json'])
    if r.returncode==0:break
    time.sleep(60)
else:raise RuntimeError('Archive not available within 14 hours; evidence remains on bridge')
a=json.loads((output/'observation01-archive.json').read_text())
r=transfer(['observation01-private.tar.gz','observation01-files.json','analysis-status.json'])
assert r.returncode==0,r.stderr
archive=output/'observation01-private.tar.gz'
with archive.open('rb') as f:digest=hashlib.file_digest(f,'sha256').hexdigest()
assert digest==a['sha256'] and archive.stat().st_size==a['bytes']
with tarfile.open(archive) as tf:tf.extractall(output/'original',filter='data')
files=json.loads((output/'observation01-files.json').read_text());original=output/'original/observation01'
for item in files:
    p=original/item['path']
    with p.open('rb') as f:digest=hashlib.file_digest(f,'sha256').hexdigest()
    assert digest==item['sha256'] and p.stat().st_size==item['bytes'],item['path']
r=subprocess.run(['python3','lab/memory-analyze.py',str(original),str(output/'independent-memory-analysis.json')],capture_output=True,text=True)
(output/'verification.json').write_text(json.dumps({'archive_sha256':a['sha256'],'files_verified':len(files),'analysis_rc':r.returncode,'analysis_stderr':r.stderr,'m8f':'OPEN','acceptance':'independent_decision_pending','p1':'GATED'},indent=2)+'\n')
print('Archive hash verified,',len(files),'files verified; descriptive analysis rc',r.returncode,flush=True)
