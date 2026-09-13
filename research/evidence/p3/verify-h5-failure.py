#!/usr/bin/env python3
"""Independent archive replay of H5 prelaunch failure; never runs archived code."""
import argparse
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import tarfile

p = argparse.ArgumentParser()
p.add_argument('archive', type=Path)
p.add_argument('--sha256', required=True)
a = p.parse_args()
if not __debug__:
    raise SystemExit('assertions required')
sha = lambda b: hashlib.sha256(b).hexdigest()
assert sha(a.archive.read_bytes()) == a.sha256


def members(t):
    result = {}
    for m in t:
        n = PurePosixPath(m.name)
        assert not n.is_absolute() and '..' not in n.parts and m.name not in result
        assert m.isdir() or m.isfile()
        result[m.name] = m
    return result


with tarfile.open(a.archive) as t:
    outer = members(t)
    data = lambda n: t.extractfile(n).read()
    read = lambda n: json.loads(data(n))
    index_name = 'controller/failure-export/SHA256.json'
    index = read(index_name)
    assert set(index) | {index_name} == {n for n, m in outer.items() if m.isfile()}
    for n, h in index.items():
        assert sha(data(n)) == h, n
    r = read('controller/minimal-001/result.json')
    latch = read('controller/FAILED.json')
    assert r['result'] == latch['result'] == 'FAILED'
    assert r['returncode'] == 1 and r['browser_result'] is None
    assert not r['target_contacted'] and r['accepted_cycles'] == r['qualification_credit'] == 0
    assert not r['browser_idle']['pids'] and not r['browser_idle_after']['pids']
    assert r['protected_inputs_unchanged'] and 'preservation_error' not in r
    assert read('controller/minimal-001/protected-before.json') == read('controller/minimal-001/protected-after.json')
    assert not any('minimal-002' in n or 'minimal-003' in n or 'functional-' in n for n in outer)
    log = data('controller/minimal-001/browser-debug.log').decode()
    assert 'AssertionError [ERR_ASSERTION]' in log and "actual: [ 'enp1s0', 'lo', 'wlo1' ]" in log
    assert "expected: [ 'lo' ]" in log
    assert '<launching>' not in log and 'SIGTRAP' not in log
    source = data('input/p3-h5-blank.cjs').decode()
    assert source.index("fs.readdirSync('/sys/class/net').sort()") < source.index('require(c.playwright)')
    assert not any(n.endswith(('/launch-contract.json', '/launch-audit.json')) for n in outer)
    contract = read('input/contract.json')
    assert sha(data('input/contract.json')) == 'cac55c25be2b1332211e806cbeac4c4edb1c2dda70f163d31e446e515a80755d'
    assert contract['uid'] == 994 and contract['gid'] == 982 and contract['groups'] == [982]
    assert contract['passwd'].split(':')[5:] == [contract['home'], '/usr/sbin/nologin']
    assert contract['account_status'].split()[1] == 'L'
    assert contract['environment']['HOME'] == contract['home'] == '/var/lib/blikvm-p3-h5/home'
    assert 'TMPDIR' not in contract['environment'] and 'XDG_RUNTIME_DIR' not in contract['environment']
    assert contract['environment']['DEBUG'] == 'pw:browser*'
    assert contract['launch_options'] == {'headless': False}
    assert contract['xvfb_arguments'] == ['-a', '-s', '-screen 0 1600x1200x24 -nolisten tcp']
    assert contract['playwright_version'] == '1.58.2'
    assert contract['playwright_sha256'] == '718c91812946dcfbb4b724cfa0084ee3be205c571df09094f218bc4571f43c2b'
    assert contract['chromium_sha256'] == '481fea1516a1f2b76454664272f12cd9dd1f20117b21e1f1498e08bc7f872c00'
    assert contract['nss_certificates'].count('H5 enrolled public CA') == 1
    assert 'no keys found' in contract['nss_keys']
    for m in contract['runtime_manifest'].values():
        assert m['uid'] == 0 and not m['mode'] & 0o022
        assert not {'system.posix_acl_access', 'system.posix_acl_default'} & m['xattrs'].keys()
    operations = 0
    for phase in ('before', 'after-seal'):
        gate = read('controller/minimal-001/'+phase+'-audit.json')
        e = gate['effective']
        assert gate['returncode'] == 0 and (e['uid'], e['gid'], e['groups']) == (994, 982, [982])
        assert all(o['passed'] for o in e['operations'])
        assert e['writable_leaves'] == ([r['leaf']] if phase == 'before' else [])
        operations += len(e['operations'])
        for barrier in gate['requirements']['barriers']:
            assert any(o['path'] == barrier and o['operation'] == 'traverse' and o['errno'] in (1, 13) for o in e['operations'])
        if phase == 'after-seal':
            assert r['seal']['sealed'] in gate['requirements']['barriers']
    seal = r['seal']
    assert seal['method'] == 'atomic_rename_under_root_0700' and not seal['browser_exit']['pids']
    archive_name = 'controller/'+PurePosixPath(seal['archive']).name
    assert sha(data(archive_name)) == seal['sha256']
    expected = read('controller/'+PurePosixPath(seal['manifest']).name)['paths']
    with tarfile.open(fileobj=io.BytesIO(data(archive_name))) as inner:
        im = members(inner)
        assert len(im) == len(expected) == 7
        for n, m in im.items():
            old = expected[str(PurePosixPath(r['leaf']).parent/n)]
            assert (m.uid, m.gid, m.mode) == (old['uid'], old['gid'], old['mode'])
            current = outer['sealed/'+n]
            assert (current.uid, current.gid, current.mode) == (m.uid, m.gid, m.mode)
            if m.isfile():
                assert sha(inner.extractfile(m).read()) == sha(data('sealed/'+n)) == old['sha256']
    provenance = read('controller/failure-export/source-provenance.json')
    assert provenance['recorded_after_failure'] and not provenance['in_process_launch_contract_complete']
    assert provenance['h3_root_cause'] == 'UNASSIGNED' and provenance['browser_launches'] == 0
    for name, field in [('p3-h5.py', 'h5_controller_sha256'), ('p3-h5-blank.cjs', 'h5_probe_sha256')]:
        assert sha(data('input/'+name)) == provenance[field]
    assert sha(data('controller/plan.md')) == provenance['plan_sha256']
    print(json.dumps({'result': 'H5_PRELAUNCH_FAILURE_CONFIRMED', 'archive_sha256': a.sha256,
        'indexed_files': len(index), 'runtime_manifest_entries': len(contract['runtime_manifest']),
        'permission_audits': 2, 'permission_operations': operations, 'sealed_members': len(expected),
        'browser_launches': 0, 'complete_in_process_launch_contracts': 0, 'generated_argv_records': 0,
        'target_contacted': False, 'qualification_credit': 0, 'accepted_cycles': 0,
        'protected_inputs_unchanged': True, 'h3_root_cause': 'UNASSIGNED'}, indent=2))
