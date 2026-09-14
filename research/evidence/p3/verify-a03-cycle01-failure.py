#!/usr/bin/env python3
"""Replay immutable attempt-03 journal-classification failure, with zero credit."""
import ast
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import runpy
import sys
import tarfile

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT/'out/p3-controller-r1'
ORIGINAL_SHA = '58ef027fa82066b505827133b488005aa22d4d15f543b8a73ab96715e02abccb'
FAILURE_SHA = '689e2442510781009439ff70ded02365b472f1492d27cbee0cf7d046ce91afd2'
sha = lambda data: hashlib.sha256(data).hexdigest()


def load(path, digest):
    assert sha(path.read_bytes()) == digest, 'archive identity'
    files = {}; names = set()
    with tarfile.open(path) as t:
        for member in t:
            p = PurePosixPath(member.name)
            assert not p.is_absolute() and '..' not in p.parts
            assert member.name not in names and (member.isfile() or member.isdir())
            names.add(member.name)
            if member.isfile(): files[member.name] = t.extractfile(member).read()
    return files


def verify():
    assert __debug__, 'assertions required'
    data = load(BASE/'p3-a03-cycle001-replay-failed.tar.gz', FAILURE_SHA)
    original = load(BASE/'p3-a03-cycle-001.tar.gz', ORIGINAL_SHA)
    for name, content in original.items(): assert data[name] == content, name
    j = lambda name: json.loads(data[name])
    index_name = 'controller/export-p3-a03-cycle001-replay-failed/SHA256.json'
    index = j(index_name)
    assert set(index) | {index_name} == set(data)
    for name, digest in index.items(): assert sha(data[name]) == digest, name
    fail = j('controller/P3_A03_FAILED.json')
    assert fail['result'] == 'FAILED' and fail['phase'] == 'independent_vm_replay'
    assert fail['attempt'] == 3 and fail['cycle'] == 1 and fail['accepted_cycles'] == 0
    assert fail['cycle_archive_sha256'] == ORIGINAL_SHA and fail['replay_exit_status'] == 1
    assert not fail['thresholds_changed'] and not fail['retry'] and not fail['later_cycles_started']
    prefix = 'controller/p3-a03-cycle-001/'
    proof = 'controller/p3-a03-cycle-001-vm-replay-failure/'
    assert sha(data[proof+'replay-stderr.txt']) == fail['replay_stderr_sha256']
    assert data[proof+'verify-a03-cycle01.py'] == (ROOT/'research/evidence/p3/verify-a03-cycle01.py').read_bytes()
    declaration = j(prefix+'cycle.json'); final = j(prefix+'cycle-final.json'); result = j(prefix+'result.json')
    assert 'result' not in declaration and declaration['record'] == 'immutable_cycle_declaration'
    assert declaration['attempt'] == 3 and declaration['cycle'] == 1
    assert final['result'] == 'CYCLE_PASS_PENDING_INDEPENDENT_REPLAY'
    assert result['result'] == 'FUNCTIONAL_PASS_PENDING_VM_REPLAY'
    assert final['accepted_cycles'] == result['accepted_cycles'] == 0
    assert not result['browser_idle']['pids'] and result['protected_inputs_unchanged']
    assert j(prefix+'controller-exit.json')['ExecMainStatus'] == '0'
    assert j(prefix+'controller-exit.json')['Result'] == 'success'
    assert result['stages'] == [dict(name='msd', result='passed', launches=2), dict(name='hid', result='passed', launches=1)]
    assert j(prefix+'protected-before.json') == j(prefix+'protected-after.json')
    assert j('controller/h5r2-acceptance.json')['result'] == 'H5R2_INDEPENDENTLY_ACCEPTED'
    assert j('controller/P3_A02_FAILED.json')['result'] == 'FAILED'
    prov = j(prefix+'source-provenance.json')
    assert prov['clean'] and prov['commit'] == prov['origin_main'] == fail['controller_commit']
    for name, digest in prov['files'].items(): assert sha(data[prefix+name]) == digest
    assess = runpy.run_path(str(ROOT/'research/evidence/p3/inventory-gates.py'))['assess']
    state = runpy.run_path(str(ROOT/'lab/p3-h5r2-state.py'))['check']
    identity = j('controller/functional-preparation/p2-identity.json')
    snapshots = [j(prefix+label+'/target.json') for label in ('preboot', 'startup', 'before', 'after')]
    boot = snapshots[1]['boot_id']; old = snapshots[0]['boot_id']
    assert boot != old and boot == result['boot_id']
    for label, inv in zip(('preboot', 'startup', 'before', 'after'), snapshots):
        assess(inv, identity)
        for key in ('sd_cid', 'machine_id', 'host_public_keys', 'hash_checks'):
            assert inv[key] == snapshots[0][key]
        gate = prefix+label+'-msd-gate/'
        state(inv, j(gate+'target-state.json'), j(gate+'host.json'), expected_boot=inv['boot_id'])
    assert all(inv['boot_id'] == boot for inv in snapshots[1:])
    journal = [json.loads(line) for line in snapshots[-1]['commands']['journal_json']['stdout'].splitlines()]
    pattern = r'\bERROR\b|\bCRITICAL\b|Traceback|\[error\]|\[crit\]|segfault|EXT4-fs error|I/O error|Buffer I/O|Kernel panic|Oops:|checksum error'
    errors = [entry for entry in journal if re.search(pattern, str(entry.get('MESSAGE', '')))]
    offending = [entry for entry in errors if int(entry['__MONOTONIC_TIMESTAMP']) == 12075869]
    assert len(offending) == 2
    assert 'connect() to unix:/run/kvmd/api/kvmd.sock failed (2: No such file or directory)' in offending[0]['MESSAGE']
    assert 'auth request unexpected status: 502' in offending[1]['MESSAGE']
    # Execute the exact frozen classifier AST, without changing its time window,
    # message conditions, or any of the original evidence. A failure is required.
    source = ROOT/'research/evidence/p3/verify-h5r2-functional.py'
    assert sha(source.read_bytes()) == '32656afa330544eb64c0003d949ffdaf4ff4b4c48364b521561580d1f99d3ce8', 'frozen classifier source changed'
    tree = ast.parse(source.read_text())
    loops = [node for node in ast.walk(tree) if isinstance(node, ast.For) and
             isinstance(node.target, ast.Name) and node.target.id == 'e' and
             isinstance(node.iter, ast.Name) and node.iter.id == 'errors']
    assert len(loops) == 1
    namespace = dict(errors=errors, journal=journal, re=re, startup_errors=[], logout_resets=[])
    try:
        exec(compile(ast.Module(body=loops, type_ignores=[]), str(source), 'exec'), namespace)
    except AssertionError:
        assert namespace['ts'] == 12075869
        assert namespace['message'] == offending[0]['MESSAGE']
    else: raise AssertionError('frozen journal failure did not reproduce')
    assert len(namespace['startup_errors']) == 4
    remaining = [entry for entry in errors if int(entry['__MONOTONIC_TIMESTAMP']) > 12075869]
    later = dict(errors=remaining, journal=journal, re=re, startup_errors=[], logout_resets=[])
    exec(compile(ast.Module(body=loops, type_ignores=[]), str(source), 'exec'), later)
    assert len(later['logout_resets']) == 1
    assert 'AssertionError' in data[proof+'replay-stderr.txt'].decode()
    return dict(result='P3_A03_CYCLE_001_REPLAY_FAILURE_CONFIRMED', attempt=3, cycle=1,
                accepted_cycles=0, total_cycles=12, qualification_credit=0,
                archive_sha256=FAILURE_SHA, original_cycle_archive_sha256=ORIGINAL_SHA,
                indexed_files_verified=len(index), original_cycle_files_unchanged=len(original),
                target_hashes_matched=10690, controller_exit=0, reboot_requests_issued=1,
                chromium_launches=3, journal_records_reviewed=len(journal),
                offending_timestamp_us=12075869, offending_records=2,
                later_logout_resets_classified=len(later['logout_resets']),
                frozen_classifier_failure_reproduced=True, thresholds_changed=False,
                h5r2='ACCEPTED', p2='PASSED', p3='UNACCEPTED', p3_b_c='BLOCKED',
                m6_atx='DEFERRED', ro_overlay='DEFERRED')


if __name__ == '__main__': print(json.dumps(verify(), indent=2))
