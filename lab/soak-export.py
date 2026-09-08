#!/usr/bin/env python3
"""Copy immutable private soak evidence to a separate credential-free export.

Only verbose browser error text is sanitized. Original bytes remain private;
frame, HID, MSD and resource measurements are copied byte-for-byte.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil

p = argparse.ArgumentParser()
p.add_argument('--source', type=Path, required=True)
p.add_argument('--output', type=Path, required=True)
p.add_argument('--private-dir', type=Path, required=True)
a = p.parse_args()
source = a.source.resolve(); output = a.output.resolve()
assert source != output and source not in output.parents and not output.exists()
for f in source.rglob('*'):
    if f.is_symlink():
        assert source in f.resolve().parents, 'external evidence symlink'
shutil.copytree(source, output, symlinks=False)
password = json.loads((a.private_dir/'credentials.json').read_text())['passwd'].encode()
changes = []
for name in ('ui/browser-samples.jsonl', 'ui/browser-result.json', 'browser.log'):
    path = output/name
    if not path.exists():
        continue
    before = path.read_bytes()
    after = re.sub(rb'''(?:Cookie:|Set-Cookie:)\s*auth_token=[^\s;"'\\]+''',
                   b'[session header redacted]', before, flags=re.I)
    after = after.replace(password, b'<redacted-password>')
    if after != before:
        path.write_bytes(after)
        changes.append({'path': name, 'private_sha256': hashlib.sha256(before).hexdigest(),
                        'public_sha256': hashlib.sha256(after).hexdigest(),
                        'reason': 'verbose browser error session-header/password redaction'})
findings = []
for path in output.rglob('*'):
    if not path.is_file():
        continue
    data = path.read_bytes()
    if (password in data or re.search(rb'-----BEGIN [A-Z ]*PRIVATE KEY-----', data)
            or re.search(rb'(?:Cookie:|Set-Cookie:)\s*auth_token=', data, re.I)):
        findings.append(str(path.relative_to(output)))
report = {'result': 'failed' if findings else 'passed', 'redactions': changes, 'findings': findings,
          'source_is_private_and_unchanged': True}
(output/'export-audit.json').write_text(json.dumps(report, indent=2)+'\n')
print(json.dumps(report))
raise SystemExit(bool(findings))
