"""Archive diagnostic evidence only; never changes target or decides acceptance."""
import hashlib,json,os,subprocess,tarfile,time
from pathlib import Path
os.chdir('/home/user/blikvm-msd')
root=Path('m8f1/observation01')
while not (root/'result.json').exists():
 time.sleep(30)
result=json.loads((root/'result.json').read_text())
review=Path('m8f1/observation01-analysis.json')
p=subprocess.run(['python3','lab/memory-analyze.py',str(root),str(review)],capture_output=True,text=True)
Path('m8f1/analysis-status.json').write_text(json.dumps({'returncode':p.returncode,'stderr':p.stderr,'acceptance':'not_decided','m8f':'OPEN'},indent=2)+'\n')
files=[]
for path in sorted(root.rglob('*')):
 if path.is_file() and not path.is_symlink():
  with path.open('rb') as f: digest=hashlib.file_digest(f,'sha256').hexdigest()
  files.append({'path':str(path.relative_to(root)),'bytes':path.stat().st_size,'sha256':digest})
index=Path('m8f1/observation01-files.json')
index.write_text(json.dumps(files,indent=2)+'\n')
archive=Path('m8f1/observation01-private.tar.gz')
with tarfile.open(archive,'x:gz') as tf:
 for item in files: tf.add(root/item['path'],arcname='observation01/'+item['path'],recursive=False)
 tf.add(index,arcname='files.json')
 if review.exists(): tf.add(review,arcname='analysis.json')
os.chmod(archive,0o600)
os.chown(archive,1000,1000)
with archive.open('rb') as f:digest=hashlib.file_digest(f,'sha256').hexdigest()
Path('m8f1/observation01-archive.json').write_text(json.dumps({'files':len(files),'bytes':archive.stat().st_size,'sha256':digest,'private':True,'diagnostic_result':result['result'],'analysis_rc':p.returncode,'independent_review':'pending','m8f':'OPEN','p1':'GATED'},indent=2)+'\n')
