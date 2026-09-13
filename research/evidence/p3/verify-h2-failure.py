#!/usr/bin/env python3
"""Independent replay of the failed H2 pre-launch permission audit.

Checks immutable archives and syscall evidence; never awards qualification.
Does not extract private evidence or execute any bridge controller code.
"""
import argparse
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import runpy
import re
import stat
import tarfile

if not __debug__:
    raise SystemExit('Evidence replay requires assertions enabled')
p = argparse.ArgumentParser()
p.add_argument('archive', type=Path)
p.add_argument('--sha256', required=True)
p.add_argument('--attempt01-archive', type=Path, default=Path('out/p3/preparation/a01-evidence.tar.gz'))
p.add_argument('--first-preflight-archive', type=Path, default=Path('out/p3/preparation/a02-preflight01-evidence.tar.gz'))
a = p.parse_args()
assert hashlib.sha256(a.archive.read_bytes()).hexdigest() == a.sha256
assess = runpy.run_path(str(Path(__file__).with_name('inventory-gates.py')))['assess']


def digest(data):
    return hashlib.sha256(data).hexdigest()


def members(t):
    result = {}
    for m in t:
        path = PurePosixPath(m.name)
        assert not path.is_absolute() and '..' not in path.parts
        assert m.name not in result and (m.isfile() or m.isdir())
        result[m.name] = m
    return result


with tarfile.open(a.archive) as t:
    entries = members(t)
    def data(name):
        return t.extractfile('attempt/'+name).read()
    def read(name):
        return json.loads(data(name))
    manifest = read('SHA256.json')
    assert {n.removeprefix('attempt/') for n, m in entries.items() if m.isfile()} == set(manifest)|{'SHA256.json'}
    for n, sha in manifest.items():
        assert digest(data(n)) == sha, n
    prefix = 'preflight-001/controller/'
    r = read(prefix+'result.json')
    assert r['result'] == 'FAILED' and not r['stages']
    assert r['accepted_cycles'] == r['qualification_credit'] == r['reboots'] == 0
    assert not r['target_repair'] and 'permission syscall audit failed' in r['error']
    assert read('controller/FAILED.json')['error'] == r['error']
    assert not any('preflight-002/' in n or 'preflight-003/' in n for n in entries)
    assert not any(n.endswith('/browser-result.json') or n.endswith('/harness.log') for n in entries)
    perm = read(prefix+'msd-before-boundary.json')
    e = perm['effective']
    assert (e['uid'],e['gid'],e['groups']) == (995,983,[983])
    assert perm['returncode'] == 1 and len(e['operations']) == 151
    assert all(o['passed'] for o in e['operations'][:-1])
    failed = e['operations'][-1]
    parent = '/home/user/blikvm-msd/p3-context/a01-smoke/browser-msd'
    assert str(Path(failed['path']).parent) == parent
    assert failed['operation'] == 'create' and failed['expected'] == 'deny'
    assert failed['outcome'] == 'allowed' and failed['errno'] == 0 and not failed['passed']
    m = perm['requirements']['protected'][parent]
    assert m['mode'] == 0o777 and m['uid'] == m['gid'] == 0 and m['xattrs'] == {}
    before = read(prefix+'protected-before.json')
    after = read('controller/failure-review/protected-after.json')
    assert set(after)-set(before) == {failed['path']} and not set(before)-set(after)
    assert [n for n in before if before[n] != after[n]] == [parent]
    for k in before[parent]:
        if k not in ('mtime_ns','ctime_ns'):
            assert before[parent][k] == after[parent][k]
    probe = after[failed['path']]
    assert probe['size'] == 0 and probe['uid'] == 995 and probe['gid'] == 983
    assert probe['sha256'] == digest(b'')
    assert all(before[n].get('sha256') == after[n].get('sha256') for n in before)
    assert read('controller/failure-review/browser-processes.json')['pids'] == []
    expected_archives = {
        '/home/user/blikvm-p3/a01-evidence.tar.gz': 'dde56c3bf3ab1d14006c601c8c8a05343c353b11c385f9b8a33755837ed5e57a',
        '/home/user/blikvm-p3/a02-preflight01-evidence.tar.gz': 'c528cd34d02e0a939edd4bbb7dfec7be6e7ff5dc83854472604154e4bfea0f6f',
        '/home/user/blikvm-p3/a02-preflight02-evidence.tar.gz': 'be15a52352e74b222e219a0ead96f10aa523eefc26d4f4bbe266afa4fad0d644'}
    assert all(before[n]['sha256'] == after[n]['sha256'] == sha for n, sha in expected_archives.items())
    sealed = []
    for name in manifest:
        if name.startswith('controller/history/') and name.endswith('-sealed.json') or name == prefix+'failure-seal.json':
            record = read(name)
            archive_name = record['archive'].split('/attempt/',1)[1]
            assert digest(data(archive_name)) == record['sha256']
            original, final = record['original'], record['sealed']
            root = min(original, key=lambda n: len(Path(n).parts))
            with tarfile.open(fileobj=io.BytesIO(data(archive_name))) as inner:
                im = members(inner)
                assert len(im) == len(original)
                for entry, tar_meta in im.items():
                    path = str(Path(root).parent/entry)
                    old, new = original[path], final[path]
                    assert (tar_meta.uid,tar_meta.gid,tar_meta.mode) == (old['uid'],old['gid'],old['mode'])
                    assert new['uid'] == new['gid'] == 0 and not new['xattrs']
                    assert new['mode'] == (0o500 if new['type'] == stat.S_IFDIR else 0o400)
                    if tar_meta.isfile():
                        assert digest(inner.extractfile(tar_meta).read()) == old['sha256'] == new['sha256']
                    if archive_name.startswith('preflight-001/'):
                        outer = 'attempt/preflight-001/browser-msd'+path.removeprefix(root)
                        sm = entries[outer]
                        assert (sm.uid,sm.gid,sm.mode) == (new['uid'],new['gid'],new['mode'])
            sealed.append(root)
    assert len(sealed) == 10
    b = read(prefix+'before/target.json')
    f = read(prefix+'failure-preservation/target.json')
    assert digest(a.attempt01_archive.read_bytes()) == expected_archives['/home/user/blikvm-p3/a01-evidence.tar.gz']
    with tarfile.open(a.attempt01_archive) as original_archive:
        original = json.load(original_archive.extractfile('cycle/startup/target.json'))
        identity = json.load(original_archive.extractfile('preparation/p2-identity.json'))
    for k in ('hash_checks','machine_id','host_public_keys','boot_id','sd_cid'):
        assert b[k] == original[k]
    for inv in (b,f):
        assess(inv, identity)
    for k in ('hash_checks','machine_id','host_public_keys','boot_id','sd_cid'):
        assert b[k] == f[k]
    assert b['boot_id'] == 'eecefe38-98a3-406c-9260-3e51de321ffe'
    def generations(inv):
        return [l for key in ('services','ssh_show') for l in inv['commands'][key]['stdout'].splitlines()
                if l.startswith(('Id=','InvocationID=','ExecMainStartTimestampMonotonic=','NRestarts='))]
    assert generations(b) == generations(f) == generations(original)
    assert digest(a.first_preflight_archive.read_bytes()) == expected_archives['/home/user/blikvm-p3/a02-preflight01-evidence.tar.gz']
    with tarfile.open(a.first_preflight_archive) as old_archive:
        prior = json.load(old_archive.extractfile('inventory/after/target.json'))
    def errors(inv):
        journal = [json.loads(l) for l in inv['commands']['journal_json']['stdout'].splitlines()]
        pattern = r'\berror\b|\bcritical\b|\bfailed\b|Traceback|segfault|Kernel panic|Oops'
        return [(j['__MONOTONIC_TIMESTAMP'],j.get('_SYSTEMD_UNIT'),j.get('MESSAGE')) for j in journal
                if re.search(pattern,str(j.get('MESSAGE','')),re.I)]
    assert errors(b) == errors(f) == errors(prior) and len(errors(f)) == 9
    for source in Path(__file__).resolve().parents[3].joinpath('lab').glob('p3-h2-*.py'):
        assert digest(source.read_bytes()) == digest(data(prefix+'sources/'+source.name))
    result = dict(result='FAILED_CONFIRMED', scope='P3-H2', accepted_cycles=0,
                  qualification_credit=0, browser_smokes_completed=0, reboots=0,
                  archive_sha256=a.sha256, verified_members=len(manifest),
                  failure_operation=failed, historical_directory_mode='0777',
                  original_archives_unchanged=True, existing_protected_file_contents_unchanged=True,
                  protected_directory_mutations=1, probe_files_created=1, probe_preserved=True,
                  metadata_archives_verified=len(sealed), sealed_working_copies_not_qualification=True,
                  target_hashes_matched=10690, boot_id=b['boot_id'],
                  service_generations_unchanged=True, browser_processes_remaining=0,
                  full_journal_records_reviewed=len(f['commands']['journal_json']['stdout'].splitlines()),
                  historical_error_messages_unchanged=9, new_error_messages=0)
print(json.dumps(result, indent=2))
