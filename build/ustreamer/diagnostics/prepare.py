#!/usr/bin/env python3
"""Prepare an isolated diagnostic source tree on the VM. Never deploys anything."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tarfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
PINS = {
    ROOT/'out/ustreamer/downloads/ustreamer.tar.gz':
        'af99973b821b1e06ad9dbebc063ceb8ca868e06af7a6ccd90e67dc1d0a7fafea',
    HERE.parent/'capture-controls.patch':
        '7b425f0954c25e35176f59aca157cfe2148b710c9ba40b119438d9a220e8cf4e',
}


def prepare(output):
    hashes = {}
    for path, expected in PINS.items():
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != expected:
            raise ValueError('Frozen input hash mismatch: '+str(path))
        hashes[str(path.relative_to(ROOT))] = actual
    output.mkdir(parents=True, exist_ok=False)
    with tarfile.open(next(iter(PINS)), 'r:gz') as tar:
        for member in tar.getmembers():
            parts = Path(member.name).parts
            if len(parts) < 2:
                continue
            member.name = str(Path(*parts[1:]))
            tar.extract(member, output, filter='data')
    for patch in (HERE.parent/'capture-controls.patch', HERE/'jpeg-tail-diagnostic.patch'):
        subprocess.run(['patch', '--batch', '--fuzz=0', '-p1', '-i', str(patch)], cwd=output, check=True)
        hashes[str(patch.relative_to(ROOT))] = hashlib.sha256(patch.read_bytes()).hexdigest()
    for name in ('taildiag.c','taildiag.h'):
        if (output/'src/libs'/name).read_bytes() != (HERE/name).read_bytes():
            raise ValueError('Generated patch differs from reviewed helper: '+name)
    hashes.update({str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
                   for p in (ROOT/'lab/stream-client.py', ROOT/'lab/soak-video.py', ROOT/'lab/verify-core-soak.py')})
    manifest = dict(diagnostic_only=True, deployed=False, qualification='NOT_RUN',
                    upstream_commit='db87e03ce769d06ba62314ca7537e1cb3369b4de',
                    git_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
                    git_status=subprocess.check_output(['git','status','--short'],cwd=ROOT,text=True),
                    hashes=hashes)
    (output/'diagnostic-source-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    return manifest


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True)
    print(json.dumps(prepare(p.parse_args().output.resolve()),indent=2))
