#!/usr/bin/env python3
"""Independent, archive-only publication replay. Never imports the controller."""
import hashlib
import json
from pathlib import Path, PurePosixPath
import sys
import tarfile

ROOT = Path(__file__).resolve().parents[3]
CASES = ('success', 'pre-reboot', 'reboot-request', 'startup-recovery',
         'firmware-chain', 'msd', 'hid', 'seal', 'cycle-final.json', 'result.json',
         'hid+seal', 'result.json-after-write', 'frozen-old')
sha = lambda data: hashlib.sha256(data).hexdigest()


def verify(path, expected):
    assert __debug__, 'assertions required'
    assert sha(path.read_bytes()) == expected, 'archive hash mismatch'
    total = 0
    with tarfile.open(path) as archive:
        members = {}
        for m in archive:
            p = PurePosixPath(m.name)
            assert not p.is_absolute() and '..' not in p.parts
            assert m.name not in members and (m.isfile() or m.isdir())
            members[m.name] = m
        def data(name): return archive.extractfile(members[name]).read()
        def read(name): return json.loads(data(name))
        summary = read('evidence/summary.json')
        assert summary['result'] == 'PUBLICATION_REHEARSAL_PASS'
        assert summary['qualification_credit'] == 0 and not summary['target_contact'] and summary['browser_launches'] == 0
        assert summary['cases'] == list(CASES[:-1]) and summary['old_bug_reproduced']
        for name, digest in summary['source_sha256'].items():
            assert sha(data(name)) == digest == sha((ROOT/name).read_bytes()), name
        for case in CASES:
            prefix = 'evidence/'+case+'/'
            report = read(prefix+'ledger.json'); paths = report['paths']
            assert report['qualification_credit'] == 0 and report['original_bytes_unchanged']
            for name, digest in report['published_sha256'].items():
                assert sha(data(prefix+name)) == digest, name
                total += 1
            old = case == 'frozen-old'
            cycle = prefix+'controller/p3-a'+('02' if old else '03')+'-cycle-001/'
            if old:
                assert paths.count('controller/p3-a02-cycle-001/cycle.json') == 3
                assert 'reboot-command-fixture' not in report['calls']
                assert 'FileExistsError' in report['error']
                assert read(cycle+'cycle.json')['result'] == 'in_progress'
                assert read(cycle+'result.json')['result'] == 'FAILED'
                continue
            assert len(paths) == len(set(paths)), case
            latch = prefix+'controller/P3_A03_FAILED.json'
            assert (latch in members) == (case != 'success')
            assert paths.count('controller/P3_A03_FAILED.json') == (case != 'success')
            declaration = read(cycle+'cycle.json')
            assert declaration['record'] == 'immutable_cycle_declaration' and 'result' not in declaration
            assert declaration['attempt'] == 3 and declaration['cycle'] == 1 and declaration['accepted_cycles'] == 0
            assert (report['error'] is None) == (case == 'success')
            calls = report['calls']
            assert ('reboot-command-fixture' in calls) == (case != 'pre-reboot')
            if case in ('success', 'hid', 'seal', 'cycle-final.json', 'result.json', 'hid+seal', 'result.json-after-write'):
                assert 'msd-browser-fixture' in calls and 'hid-browser-fixture' in calls and 'seal' in calls
            if case in ('pre-reboot', 'reboot-request', 'startup-recovery', 'firmware-chain'):
                assert 'msd-browser-fixture' not in calls
            if case == 'msd': assert 'msd-browser-fixture' in calls and 'hid-browser-fixture' not in calls
            if case == 'success':
                assert read(cycle+'cycle-final.json')['result'] == 'CYCLE_PASS_PENDING_INDEPENDENT_REPLAY'
                assert read(cycle+'result.json')['result'] == 'FUNCTIONAL_PASS_PENDING_VM_REPLAY'
                for name in ('pre-reboot', 'reboot-request', 'startup-recovered', 'firmware-chain', 'pre-browser', 'msd-result', 'hid-result'):
                    assert cycle+name+'.json' in members
            else:
                assert read(latch)['result'] == 'FAILED' and read(latch)['accepted_cycles'] == 0
                if case == 'cycle-final.json': assert cycle+'cycle-final.json' not in members
                elif case in ('result.json', 'result.json-after-write'):
                    assert read(cycle+'cycle-final.json')['result'] == 'CYCLE_PASS_PENDING_INDEPENDENT_REPLAY'
                else: assert read(cycle+'cycle-final.json')['result'] == 'FAILED'
                if case == 'result.json': assert cycle+'result.json' not in members
                elif case == 'result.json-after-write':
                    assert read(cycle+'result.json')['result'] == 'FUNCTIONAL_PASS_PENDING_VM_REPLAY'
                else: assert read(cycle+'result.json')['result'] == 'FAILED'
    return dict(result='CONTROLLER_R1_REHEARSAL_INDEPENDENTLY_REPLAYED', archive_sha256=expected,
                cases=len(CASES), publication_bytes_verified=total, qualification_credit=0,
                target_contact=False, browser_launches=0, old_bug_reproduced=True)


if __name__ == '__main__': print(json.dumps(verify(Path(sys.argv[1]), sys.argv[2]), indent=2))
