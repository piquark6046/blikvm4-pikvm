#!/usr/bin/env python3
"""Record source identity separately from the reproducible rootfs payload."""
import hashlib
import json
from pathlib import Path
import subprocess

repo = Path(__file__).resolve().parents[2]
out = repo / 'out/ubuntu'
artifacts = out / 'artifacts'


def record(path):
    return {'size': path.stat().st_size, 'sha256': hashlib.file_digest(path.open('rb'), 'sha256').hexdigest()}


def git(*args):
    return subprocess.check_output(['git', *args], cwd=repo, text=True).strip()


result = {
    'schema_version': 1,
    'linux': {'version': '7.2.3', 'baseline': 'linux-7.2.3-usb-gadget-baseline',
              'exception': 'documented systemd-required config delta', 'modules': 'all built in'},
    'initramfs': {'distribution': 'Ubuntu Base', 'version': '26.04.1',
                  'init': '/sbin/init', 'transport': 'read-write RAM root'},
    'source': {'commit': git('rev-parse', 'HEAD'), 'status': git('status', '--porcelain'),
               'files': {str(p.relative_to(repo)): record(p)
                         for directory in ('build', 'lab', 'initramfs', 'board')
                         for p in sorted((repo / directory).rglob('*'))
                         if p.is_file() and '__pycache__' not in p.parts}},
    'ubuntu': {'archive': record(out / 'downloads/ubuntu-base-26.04.1-base-arm64.tar.gz'),
               'signer': '843938DF228D22F7B3742BC0D94AA3F0EFE21092',
               'snapshot': '20260906T000000Z', 'source_date_epoch': 1788652800,
               'signature_status': (out / 'downloads/signature-status.log').read_text()},
    'builder_image': json.loads((out / 'builder-image.json').read_text())[0]['Id'],
    'artifacts': {p.name: dict(name=p.name, **record(p)) for p in sorted(artifacts.iterdir())
                  if p.is_file() and p.name not in ('manifest.json', 'SHA256SUMS')},
    'acceptance': {'m6': 'deferred', 'm7': 'not_qualified', 'consecutive_boot_gate': 20},
}
(artifacts / 'manifest.json').write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
