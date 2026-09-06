#!/usr/bin/env python3
"""Bind the derivative payload to frozen M7 and all source/package inputs."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

repo = Path(__file__).resolve().parents[2]
out = repo / 'out/kvmd-web'
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
    upstream=dict(url='https://github.com/pikvm/kvmd', tag='v4.213',
                  commit='387846d22fa807f97de09750c32c1c9b26d36c1c',
                  archive=record(out/'downloads/kvmd.tar.gz'),
                  downstream_patches={'build/kvmd/video-only.patch':record(repo/'build/kvmd/video-only.patch'), 'build/kvmd-web/web-auth.patch':record(repo/'build/kvmd-web/web-auth.patch')}),
    baseline=dict(tag='ubuntu-26.04.1-kvmd-video-baseline', rootfs=record(repo/'out/kvmd/artifacts/rootfs.tar.gz')),
    builder_image=json.loads((out/'builder-image.json').read_text())[0]['Id'],
    artifacts={p.name:dict(name=p.name,**record(p)) for p in sorted(artifacts.iterdir())
               if p.is_file() and p.name not in ('manifest.json','SHA256SUMS')},
    acceptance=dict(m8b='not_qualified',m6='deferred',m8a='frozen'))
(artifacts/'manifest.json').write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n')
(artifacts/'SHA256SUMS').write_text(''.join(record(p)['sha256']+'  '+p.name+'\n' for p in sorted(artifacts.iterdir()) if p.is_file() and p.name!='SHA256SUMS'))
