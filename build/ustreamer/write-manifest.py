#!/usr/bin/env python3
"""Bind the derivative payload to frozen M7 and all source/package inputs."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

repo = Path(__file__).resolve().parents[2]
out = repo / 'out/ustreamer'
artifacts = Path(sys.argv[1]).resolve() if len(sys.argv)>1 else out / 'artifacts'
def record(p):
    with p.open('rb') as f:
        return dict(size=p.stat().st_size, sha256=hashlib.file_digest(f, 'sha256').hexdigest())
def git(*args):
    return subprocess.check_output(['git', *args], cwd=repo, text=True).strip()
manifest = dict(schema_version=1,
    source=dict(commit=git('rev-parse','HEAD'), status=git('status','--porcelain'),
                files={str(p.relative_to(repo)): record(p) for d in ('build','lab','initramfs','board')
                       for p in sorted((repo/d).rglob('*')) if p.is_file() and '__pycache__' not in p.parts}),
    upstream=dict(url='https://github.com/pikvm/ustreamer', tag='v6.65',
                  commit='db87e03ce769d06ba62314ca7537e1cb3369b4de',
                  archive=record(out/'downloads/ustreamer.tar.gz'),
                  downstream_patches={'build/ustreamer/capture-controls.patch':record(repo/'build/ustreamer/capture-controls.patch')}),
    baseline=dict(tag='ubuntu-26.04.1-rootfs-baseline', rootfs=record(repo/'out/ubuntu/artifacts/rootfs.tar.gz')),
    builder_image=json.loads((out/'builder-image.json').read_text())[0]['Id'],
    artifacts={p.name:dict(name=p.name,**record(p)) for p in sorted(artifacts.iterdir())
               if p.is_file() and p.name not in ('manifest.json','SHA256SUMS')},
    acceptance=dict(m75='not_qualified',m6='deferred',kvmd='not_started'))
(artifacts/'manifest.json').write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n')
(artifacts/'SHA256SUMS').write_text(''.join(record(p)['sha256']+'  '+p.name+'\n' for p in sorted(artifacts.iterdir()) if p.is_file() and p.name!='SHA256SUMS'))
