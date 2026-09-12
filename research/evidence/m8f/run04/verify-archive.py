import pathlib,json,hashlib,tarfile
r=pathlib.Path(__file__).parent;receipt=json.loads((r/'receipt.json').read_text());a=r/'archive.tar.gz'
with a.open('rb') as f:assert hashlib.file_digest(f,'sha256').hexdigest()==receipt['sha256']
assert a.stat().st_size==receipt['bytes'];index=json.loads((r/'files.json').read_text());dest=r/'original';dest.mkdir(exist_ok=False);seen=set()
with tarfile.open(a) as t:
 for m in t:
  if not m.isfile():continue
  b=t.extractfile(m).read();n=m.name.removeprefix('m8f-run04/')
  if n in index:
   assert len(b)==index[n]['size'] and hashlib.sha256(b).hexdigest()==index[n]['sha256'],n;seen.add(n)
  else:assert m.name=='m8f-run04-files.json',m.name
  p=dest/m.name;assert p.resolve().is_relative_to(dest.resolve());p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b)
assert seen==set(index)
(r/'archive-verification.json').write_text(json.dumps({'result':'passed','archive':receipt,'verified_files':len(seen),'symlinks_not_followed_or_extracted':True},indent=2)+'\n');print('verified',len(seen),'files')
