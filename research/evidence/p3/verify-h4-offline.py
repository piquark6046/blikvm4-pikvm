#!/usr/bin/env python3
"""Replay private H4 offline diagnostics; never launch a browser or contact target."""
import hashlib
import json
from pathlib import Path
import stat
import struct
import tarfile

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'out/p3-h4'
PINS = {
    'offline-diagnostics.tar.gz': '284c44c1e62f526b1bf36db42940a0356c55f38c2805877634b8b1afa8da99c0',
    'h3-crashpad-private.tar.gz': '129c99656aa0c39346c2b77e4591e787136a2b987f40c85b9fd53e90b457943e',
}


def read_archive(name):
    p = OUT / name
    assert hashlib.file_digest(p.open('rb'), 'sha256').hexdigest() == PINS[name]
    with tarfile.open(p) as t:
        entries = t.getmembers()
        assert len({m.name for m in entries}) == len(entries)
        assert all(m.isfile() for m in entries)
        return {m.name: t.extractfile(m).read() for m in entries}


def crash_frames(b):
    # Public structure definitions: google/breakpad minidump_format.h and
    # minidump_cpu_amd64.h. No raw stack contents or environment are published.
    assert struct.unpack_from('<I', b)[0] == 0x504d444d
    n, directory = struct.unpack_from('<II', b, 8)
    streams = {}
    for i in range(n):
        kind, size, rva = struct.unpack_from('<III', b, directory + i * 12)
        assert rva + size <= len(b)
        streams[kind] = (size, rva)
    e = streams[6][1]
    tid, signal = struct.unpack_from('<I', b, e)[0], struct.unpack_from('<I', b, e + 8)[0]
    assert (tid, signal) == (15228, 5)
    size, context = struct.unpack_from('<II', b, e + 160)
    assert size == 1232 and struct.unpack_from('<I', b, context + 48)[0] & 0x100000
    rbp, rip = (struct.unpack_from('<Q', b, context + o)[0] for o in (160, 248))
    m = streams[4][1]
    modules = []
    for i in range(struct.unpack_from('<I', b, m)[0]):
        base, size, _, _, name = struct.unpack_from('<QIIII', b, m + 4 + i * 108)
        length = struct.unpack_from('<I', b, name)[0]
        modules.append((base, size, Path(b[name+4:name+4+length].decode('utf-16-le')).name))
    def module(address):
        for base, size, name in modules:
            if base <= address < base + size:
                return {'module': name, 'offset': hex(address-base)}
        raise AssertionError('frame outside retained modules')
    m = streams[5][1]
    ranges = [struct.unpack_from('<QII', b, m + 4 + i * 16)
              for i in range(struct.unpack_from('<I', b, m)[0])]
    frames = [module(rip)]
    for _ in range(32):
        matching = [(a, s, r) for a, s, r in ranges if a <= rbp and rbp + 16 <= a + s]
        if not matching:
            break
        assert len(matching) == 1
        start, _, rva = matching[0]
        nextbp, ret = struct.unpack_from('<QQ', b, rva + rbp - start)
        frames.append(module(ret))
        if nextbp <= rbp:
            break
        rbp = nextbp
    return {'thread': tid, 'signal': signal, 'frames': frames,
            'method': 'saved AMD64 RIP and bounded RBP chain; no CFI unwinding or symbols',
            'root_cause': 'UNASSIGNED'}


def main():
    files = read_archive('offline-diagnostics.tar.gz')
    indexed = json.loads(files['archive-members.json'])
    assert set(files) == set(indexed) | {'archive-members.json'}
    for name, expected in indexed.items():
        assert len(files[name]) == expected['bytes']
        assert hashlib.sha256(files[name]).hexdigest() == expected['sha256']
    data = json.loads(files['metadata-and-review/browser-runtime-metadata-diff.json'])
    a, b = (data['manifests'][k] for k in ('known_good', 'h3'))
    assert set(a) == set(b)
    common = [p for p in a if a[p]['type'] == b[p]['type'] == stat.S_IFREG]
    assert all(a[p]['sha256'] == b[p]['sha256'] for p in common)
    helper = 'browsers/chromium-1208/chrome-linux64/chrome_sandbox'
    assert (a[helper]['uid'], a[helper]['gid'], a[helper]['st_mode']) == (1000, 1000, 0o100755)
    assert (b[helper]['uid'], b[helper]['gid'], b[helper]['st_mode']) == (0, 0, 0o100755)
    assert a[helper]['getcap'] == b[helper]['getcap'] == ''
    assert a[helper]['xattrs'] == b[helper]['xattrs'] == {}
    assert not any(v['st_mode'] & 0o7000 for tree in (a, b) for v in tree.values())
    review = 'metadata-and-review/review/'
    copy = json.loads(files[review+'copy-integrity.json'])
    assert copy['copy_manifest'] == a
    assert all(copy[k] for k in ('known_good_unchanged', 'h3_runtime_unchanged', 'copy_manifest_equal'))
    kernel = json.loads(files[review+'matrix-kernel.json'])['stdout']
    cases = []
    for case in 'ABCD':
        record = json.loads(files[f'matrix02-controller/{case}-completed.json'])
        result = record['result']
        log = files[f'matrix02-controller/{case}-stderr.log'].decode()
        launch = next(line for line in log.splitlines() if '<launching>' in line)
        assert '--no-sandbox' not in launch
        assert result['options']['chromiumSandbox'] is True
        assert (result['uid'], result['gid'], result['groups']) == (995, 983, [983])
        assert record['returncode'] == 1 and not result['page_created'] and not result['about_blank']
        assert 'No usable sandbox!' in log and 'signal=SIGTRAP' in log
        assert record['interfaces'].split()[0] == 'lo' and len(record['interfaces'].splitlines()) == 1
        assert 'apparmor="AUDIT"' in kernel and f'execpath="{record["executable"]}"' in kernel
        assert files[f'matrix02-controller/{case}-processes.jsonl']
        cases.append({'case': case, 'page_created': False, 'signal': 'SIGTRAP', 'fatal': 'No usable sandbox!'})
    assert kernel.count('profile="unprivileged_userns"') == 4
    assert json.loads(files[review+'browser-processes.json'])['returncode'] == 1
    assert 'signal=SIGTRAP' in files[review+'h3-browser-result.txt'].decode()
    assert '--no-sandbox' in files[review+'h3-browser-result.txt'].decode()
    assert files[review+'h3-browser-log.txt'] == b''
    with tarfile.open(ROOT/'out/p3-h3/h3-failed.tar.gz') as t:
        assert files[review+'h3-failed-latch.txt'] == t.extractfile('controller/FAILED.json').read()
    dumps = read_archive('h3-crashpad-private.tar.gz')
    dump = next(v for k, v in dumps.items() if k.endswith('.dmp'))
    assert len(dump) == 51376
    # Private requested artifact, separate from the sanitized public conclusion.
    destination = OUT/'browser-runtime-metadata-diff.json'
    if not destination.exists():
        destination.touch(mode=0o600)
        destination.write_bytes(files['metadata-and-review/browser-runtime-metadata-diff.json'])
    result = {'result': 'H4_OFFLINE_BLOCKED_CONFIRMED', 'qualification_credit': 0,
              'accepted_cycles': 0, 'target_contacted': False,
              'archive_sha256': PINS, 'indexed_files_verified': len(indexed),
              'runtime_entries_each': len(a), 'common_regular_files_content_equal': len(common),
              'suid_stripping_hypothesis': 'DISPROVEN_FOR_FROZEN_SOURCE_AND_H3',
              'sandbox_helper': {'source': a[helper], 'h3': b[helper]},
              'metadata_preserving_copy_equal': True, 'cases': cases,
              'sandbox_enabled_matrix': 'SEPARATE APPARMOR FAILURE MODE',
              'h3_historical_no_sandbox_present': True,
              'current_sandbox_blocker': 'AppArmor unprivileged_userns sys_admin denial',
              'h3_crash': crash_frames(dump), 'h3_failed_latch_unchanged': True,
              'h4_qualification_namespace_created': False, 'functional_preflights_started': False,
              'p3_a_attempt02_started': False}
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
