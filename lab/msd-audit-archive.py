#!/usr/bin/env python3
"""Scan public evidence without printing private values or matching content."""
import argparse,hashlib,json,re,tarfile
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--archive',type=Path,required=True);p.add_argument('--private-dir',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
credentials=json.loads((a.private_dir/'credentials.json').read_text())
secrets=[credentials['passwd'].encode()]
for f in a.private_dir.rglob('*'):
    if not f.is_file():continue
    if f.suffix=='.key' or f.name in ('bridge_key','id_ed25519'):
        data=f.read_bytes()
        if b'PRIVATE KEY' in data:secrets.append(data)
findings=[];count=0
with tarfile.open(a.archive,'r:gz') as archive:
    for member in archive:
        assert not member.name.startswith('/') and '..' not in Path(member.name).parts
        if not member.isfile():continue
        count+=1;data=archive.extractfile(member).read()
        if any(s and s in data for s in secrets) or re.search(rb'-----BEGIN [A-Z ]*PRIVATE KEY-----',data) or re.search(rb'(?:Cookie:|Set-Cookie:)\s*auth_token=',data,re.I):
            findings.append(member.name)
r={'result':'failed' if findings else 'passed','archive_sha256':hashlib.file_digest(a.archive.open('rb'),'sha256').hexdigest(),'files_scanned':count,'findings':findings}
a.output.write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r));raise SystemExit(bool(findings))
