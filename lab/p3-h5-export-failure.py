#!/usr/bin/env python3
"""Archive H5's failed prelaunch probe; no browser retry or target contact."""
import json
import os
from pathlib import Path
import runpy
import shutil
import subprocess
import tarfile

P = runpy.run_path(str(Path(__file__).with_name('p3-h5.py')))
B = P['BASE']; H = P['H']; P['idle'](); os.umask(0o077)
assert P['read'](B/'controller/FAILED.json')['result'] == 'FAILED'
assert not list((B/'active').iterdir())
snapshot = B/'controller/failure-export'
snapshot.mkdir(mode=0o700)
for name, cmd in {
    'journal.log': ['journalctl', '-u', 'blikvm-p3-h5-minimal-001', '--no-pager', '-o', 'short-monotonic'],
    'unit.txt': ['systemctl', 'show', 'blikvm-p3-h5-minimal-001', '--no-pager'],
    'account.txt': ['getent', 'passwd', 'p3-browser-h5'],
    'groups.txt': ['id', 'p3-browser-h5'],
    'mountinfo.txt': ['cat', '/proc/self/mountinfo'],
}.items():
    (snapshot/name).write_bytes(subprocess.check_output(cmd))
shutil.copyfile(__file__, snapshot/'p3-h5-export-failure.py')
P['publish'](snapshot/'source-provenance.json', {
    'recorded_after_failure': True,
    'build_vm_head_at_launch': 'eadd900a909dbcbe815fdd1eabeece85997e1cea',
    'dirty_at_launch': ['lab/p3-h5.py', 'lab/p3-h5-blank.cjs', 'research/evidence/p3/h5-plan.md'],
    'h5_controller_sha256': H['digest'](B/'input/p3-h5.py'),
    'h5_probe_sha256': H['digest'](B/'input/p3-h5-blank.cjs'),
    'plan_sha256': H['digest'](B/'controller/plan.md'),
    'target_contacted': False, 'browser_launches': 0, 'qualification_credit': 0,
    'failure_phase': 'Node prelaunch assertion on inherited sysfs interface view',
    'runtime_contract_prepared_before_probe': True,
    'in_process_launch_contract_complete': False,
    'generated_browser_argv_available': False,
    'h3_root_cause': 'UNASSIGNED',
})
roots = [B/'controller', B/'sealed'] + [p for p in (B/'input').iterdir() if p.name != 'runtime']
index = {}
for root in roots:
    for p in ([root] if root.is_file() else root.rglob('*')):
        if p.is_file():
            index[str(p.relative_to(B))] = H['digest'](p)
P['publish'](snapshot/'SHA256.json', index)
exports = Path('/home/user/blikvm-p3-h5-exports')
exports.mkdir(mode=0o700); os.chown(exports, 1000, 1000)
archive = exports/'h5-failed.tar.gz'
with archive.open('xb') as f:
    with tarfile.open(fileobj=f, mode='w:gz', dereference=False) as t:
        for root in roots:
            t.add(root, arcname=str(root.relative_to(B)))
    f.flush(); os.fsync(f.fileno())
archive.chmod(0o400); os.chown(archive, 1000, 1000)
print(json.dumps({'sha256': H['digest'](archive), 'bytes': archive.stat().st_size, 'indexed': len(index)}))
