#!/usr/bin/env python3
"""Recover sanitized historical facts without launching or executing archive code.

Unknown historical fields stay unknown. H2's unexecuted configuration must not
be represented as a successful launch. Raw archives and dump remain private.
"""
import hashlib
import json
from pathlib import Path
import shlex
import struct
import tarfile

ROOT = Path(__file__).resolve().parents[4]
DEST = Path(__file__).resolve().parent
PINS = {
    'h2': ('out/p3-h2/h2-failed-evidence.tar.gz', '1bb8f7076d86de563381e2736169698589c03f728f5d09c6fac148943b42b332'),
    'h3': ('out/p3-h3/h3-failed.tar.gz', '78cb138eca5698b29286931df1c47c350b3526c13560f35a812babc51ef48752'),
    'earlier_good': ('out/p3/preparation/a02-preflight01-evidence.tar.gz', 'c528cd34d02e0a939edd4bbb7dfec7be6e7ff5dc83854472604154e4bfea0f6f'),
    'h4': ('out/p3-h4/offline-diagnostics.tar.gz', '284c44c1e62f526b1bf36db42940a0356c55f38c2805877634b8b1afa8da99c0'),
    'dump': ('out/p3-h4/h3-crashpad-private.tar.gz', '129c99656aa0c39346c2b77e4591e787136a2b987f40c85b9fd53e90b457943e'),
}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def archive(label):
    name, expected = PINS[label]
    assert digest((ROOT / name).read_bytes()) == expected, label
    with tarfile.open(ROOT / name) as t:
        names = t.getnames()
        assert len(names) == len(set(names))
        return {m.name: t.extractfile(m).read() for m in t if m.isfile()}


def write(name, data):
    (DEST / name).write_text(json.dumps(data, indent=2, sort_keys=True) + '\n')


def unknown(reason='not captured in examined immutable evidence'):
    return {'status': 'UNKNOWN', 'reason': reason}


def source(value, member):
    return {'value': value, 'basis': 'archived source; not an observed process environment', 'member': member}


def main():
    h2, h3, good, h4, dumps = (archive(k) for k in PINS)
    h2prefix = 'attempt/preflight-001/controller/'
    h2result = json.loads(h2[h2prefix + 'result.json'])
    assert h2result['result'] == 'FAILED' and h2result['stages'] == []
    assert 'permission syscall audit failed' in h2result['error']
    assert not any(n.endswith(('/browser-result.json', '/harness.log')) for n in h2)
    good_result = json.loads(good['smoke/browser-msd/browser-result.json'])
    assert good_result['result'] == 'passed'
    assert good['smoke/browser-msd/browser.log'] == b''
    good_wrapper = good['harness/msd-browser-hil.py'].decode()
    assert "'HOME='" not in good_wrapper and 'TMPDIR' not in good_wrapper
    assert "chromium.launch({headless:false})" in good['harness/msd-browser.mjs'].decode()
    h2wrapper = h2[h2prefix + 'sources/msd-browser-hil.py'].decode()
    h2controller = h2[h2prefix + 'sources/p3-h2-preflight.py'].decode()
    assert "'HOME='+str(LEAF/'runtime-home')" in h2wrapper
    assert 'TMPDIR' not in h2wrapper + h2controller
    ctx = '/var/lib/blikvm-p3-h3/input/context'
    h3source = 'controller/snapshot-h3-failed/context/msd-browser-hil.py'
    assert "'HOME='+str(LEAF/'runtime-home')" in h3[h3source].decode()
    h3controller = h3['controller/snapshot-h3-failed/p3-h3-preflight.py'].decode()
    assert 'TMPDIR=str(tmp)' in h3controller
    error = json.loads(h3['sealed/chromium-preflight-001/msd/browser-result.json'])['error']
    argv = shlex.split(next(l.removeprefix('<launching> ') for l in error.splitlines() if l.startswith('<launching> ')))
    assert '--no-sandbox' in argv and 'signal=SIGTRAP' in error
    manifests = json.loads(h4['metadata-and-review/browser-runtime-metadata-diff.json'])['manifests']
    installation = json.loads(h3['controller/browser-installation.json'])['input_manifest']
    chrome = 'browsers/chromium-1208/chrome-linux64/chrome'
    runtime = ctx + '/out/kvmd-web/browser'
    chrome_hash = installation[runtime + '/' + chrome]['sha256']
    assert manifests['known_good'][chrome]['sha256'] == manifests['h3'][chrome]['sha256'] == chrome_hash
    env_names = ['HOME', 'TMPDIR', 'XDG_RUNTIME_DIR', 'DISPLAY', 'XAUTHORITY',
                 'NODE_EXTRA_CA_CERTS', 'PLAYWRIGHT_BROWSERS_PATH',
                 'PLAYWRIGHT_HOST_PLATFORM_OVERRIDE', 'DBUS_SESSION_BUS_ADDRESS', 'PATH']
    common = {'scope': 'P3-H4b target-free archive analysis', 'qualification_credit': 0,
              'exact_reproduction_ready': False,
              'node': unknown('historical resolved executable, bytes and version not captured'),
              'mount_flags': unknown('historical bridge mount flags not captured'),
              'environment': {k: unknown() for k in env_names},
              'xvfb_arguments': ['-a', '-s', '-screen 0 1600x1200x24 -nolisten tcp'],
              'launch_options': {'headless': False},
              'playwright_version': unknown('package hash retained; version bytes verified separately against that hash'),
              'node_command_from_archived_wrapper': 'node'}
    h2contract = dict(common, identity='H2 at 0ef54c7', historical_outcome='FAILED_BEFORE_BROWSER_LAUNCH',
                      browser_argv=unknown('no H2 Chromium process was launched'),
                      historical_successful_control_available=False)
    h3contract = dict(common, identity='H3 first launch at 1895be8', historical_outcome='SIGTRAP',
                      browser_argv=argv, historical_no_sandbox_present=True,
                      chromium={'path': argv[0], 'sha256': chrome_hash})
    for c, label, cwd, leaf, member in [
        (h2contract, 'h2', '/var/lib/blikvm-p3-h2', '/var/lib/blikvm-p3-h2/attempt/preflight-001/browser-msd', h2prefix + 'sources/msd-browser-hil.py'),
        (h3contract, 'h3', ctx, '/var/lib/blikvm-p3-h3/active/chromium-preflight-001/msd', h3source),
    ]:
        c['archive'] = {'path': PINS[label][0], 'sha256': PINS[label][1]}
        c['environment'] = {k: unknown() for k in env_names}
        c['cwd'] = source(cwd, member)
        c['playwright_module'] = source(cwd + '/out/kvmd-web/browser/node_modules/playwright', member)
        for k, v in {'HOME': leaf + '/runtime-home', 'NODE_EXTRA_CA_CERTS': cwd + '/private/ca.crt',
                     'PLAYWRIGHT_BROWSERS_PATH': cwd + '/out/kvmd-web/browser/browsers',
                     'PLAYWRIGHT_HOST_PLATFORM_OVERRIDE': 'ubuntu24.04-x64'}.items():
            c['environment'][k] = source(v, member)
        c['environment']['TMPDIR'] = source(leaf + '/runtime-tmp', 'controller/snapshot-h3-failed/p3-h3-preflight.py') if label == 'h3' else unknown('no explicit H2 override; inherited effective value not captured; H2 did not launch')
        audit_member = h2prefix + 'msd-before-boundary.json' if label == 'h2' else 'controller/chromium-preflight-001/msd/launch-audit-001.json'
        audit = json.loads((h2 if label == 'h2' else h3)[audit_member])
        audit = audit['effective'] if label == 'h2' else audit
        c['identity_evidence'] = {'uid': audit['uid'], 'gid': audit['gid'], 'groups': audit['groups'], 'member': audit_member, 'kind': 'prelaunch audit'}
        c['runtime_home_layout'] = {'source_semantics': 'fresh runtime-home/.pki/nssdb copied from input; directories 0700, files 0600, owner 995:983', 'tmp': 'separate runtime-tmp 0700 owner 995:983' if label == 'h3' else 'no separately created TMPDIR'}
    h3contract['playwright_package_sha256'] = installation[runtime + '/node_modules/playwright/package.json']['sha256']
    observed = json.loads((DEST / 'h4b-bridge-readonly.json').read_text())
    assert observed['playwright']['package_sha256'] == h3contract['playwright_package_sha256']
    h3contract['playwright_version'] = {'value': observed['playwright']['version'], 'basis': 'current package bytes match frozen H3 package SHA-256'}
    h3contract['browser_runtime_tree'] = {'manifest_member': 'controller/browser-installation.json:input_manifest',
                                        'entries': sum(k.startswith(runtime + '/') or k == runtime for k in installation)}
    h3contract['nss_db_identity'] = {Path(k).name: v['sha256'] for k, v in installation.items() if k.startswith('/var/lib/blikvm-p3-h3/input/nssdb/') and 'sha256' in v}
    h2metadata = json.loads(h2[h2prefix + 'failure-original-metadata.json'])['paths']
    h2contract['nss_db_identity'] = {Path(k).name: v['sha256'] for k, v in h2metadata.items() if '/.pki/nssdb/' in k and 'sha256' in v}
    h2contract['browser_runtime_tree'] = unknown('H2 runtime symlink source measured later by H4; no successful H2 launch')
    h2contract['chromium'] = unknown('no executed H2 Chromium binary; H4 source tree hash is retrospective')
    h2contract['earlier_successful_candidate'] = {
        'identity': 'attempt02 preflight01 at 81b3f61; not H2',
        'archive_sha256': PINS['earlier_good'][1], 'browser_result': 'passed',
        'browser_version': good_result['version'], 'cwd': '/var/lib/blikvm-p3-browser',
        'HOME': 'runuser account HOME; no explicit fresh runtime-home override in archived wrapper',
        'TMPDIR': 'no explicit override; inherited effective value unknown',
        'exact_browser_argv': unknown('successful browser.log is empty; browser-result has no argv'),
        'source_member': 'harness/msd-browser-hil.py',
        'substitution_status': 'requires resolution of requested good-control identity',
    }
    differences = [
        {'dimension': 'observed launch', 'h2': 'never launched', 'h3': 'SIGTRAP at first launch'},
        {'dimension': 'TMPDIR override', 'h2': 'none explicit; inherited unknown', 'h3': 'browser-owned runtime-tmp exported', 'priority': 'D1 only after valid controls'},
        {'dimension': 'browser runtime', 'h2': 'source symlink; retrospective H4 source manifest', 'h3': 'root-owned copied input distribution; archived H3 manifest'},
        {'dimension': 'runtime metadata (H4 measurement)', 'details': '1235 entries each; 1147 common regular files equal; all owners become root; 640 full-mode differences; two CLI symlinks dereferenced'},
        {'dimension': 'HOME', 'h2': h2contract['environment']['HOME'], 'h3': h3contract['environment']['HOME']},
        {'dimension': 'NSS', 'hashes_equal': h2contract['nss_db_identity'] == h3contract['nss_db_identity'], 'launch_time_effective_state': 'H2 did not launch'},
        {'dimension': 'cwd/context', 'h2': '/var/lib/blikvm-p3-h2', 'h3': ctx},
        {'dimension': 'prelaunch JS', 'h2': 'boundary audit outside JS', 'h3': 'additional synchronous h3LaunchGate before each chromium.launch'},
        {'dimension': 'P3_CONTROL', 'h2': 'control-msd under attempt/preflight-001', 'h3': 'input/acks/chromium-preflight-001-msd plus P3_LAUNCH_REQUIREMENTS'},
        {'dimension': 'ancestor isolation', 'h2': 'sealed descendants; audit failed on historical writable ancestor', 'h3': 'ancestor quarantine and separate input/active/sealed/controller'},
    ]
    diff = {'status': 'BLOCKED_HISTORICAL_GOOD_CONTROL_UNRESOLVED', 'root_cause': 'UNASSIGNED',
            'exhaustive_effective_environment_diff_possible': False, 'differences': differences,
            'unknowns': ['successful H2 launch identity', 'good-control exact browser argv', 'historical Node path/hash/version', 'inherited environment', 'historical DISPLAY/XAUTHORITY', 'historical bridge mount flags'],
            'probes_started': 0, 'target_contacted': False, 'qualification_credit': 0,
            'decision_A_B_C_D': None, 'reason': 'No valid paired historical controls; cannot classify runtime drift or nonreproduction without valid probes'}
    # Read only module identity and exception data from the private minidump.
    dump = next(v for k, v in dumps.items() if k.endswith('.dmp'))
    n, directory = struct.unpack_from('<II', dump, 8)
    streams = {}
    for i in range(n):
        kind, size, rva = struct.unpack_from('<III', dump, directory + 12*i)
        assert rva + size <= len(dump)
        streams[kind] = rva
    exception = streams[6]
    thread = struct.unpack_from('<I', dump, exception)[0]
    signal = struct.unpack_from('<I', dump, exception + 8)[0]
    assert (thread, signal) == (15228, 5)
    modules = streams[4]
    build_id = None
    for i in range(struct.unpack_from('<I', dump, modules)[0]):
        record = modules + 4 + i*108
        name_rva = struct.unpack_from('<I', dump, record + 20)[0]
        size = struct.unpack_from('<I', dump, name_rva)[0]
        name = dump[name_rva+4:name_rva+4+size].decode('utf-16-le')
        if Path(name).name == 'chrome':
            size, cv = struct.unpack_from('<II', dump, record + 76)
            assert dump[cv:cv+4] == b'LEpB'
            build_id = dump[cv+4:cv+size].hex()
    assert build_id == '3693ce542c8bad6e9045e9f05df6241a3ec45cd4'
    crash = {'signal': 'SIGTRAP', 'signal_number': signal, 'crashing_thread': thread,
             'module': 'chrome', 'module_sha256': chrome_hash, 'module_build_id': build_id,
             'instruction_offset': '0x633662b', 'root_cause': 'UNASSIGNED',
             'frames': json.loads((DEST / 'offline-result.json').read_text())['h3_crash']['frames'],
             'frame_method': 'saved RIP and bounded RBP chain; no CFI unwinding',
             'stderr': 'empty browser.log; retained browser-result contains launch and SIGTRAP without CHECK/FATAL text',
             'symbolization': 'available addr2line on hash-matching stripped binary returns no source lines; nearest exported names are not reliable function identification',
             'raw_dump_published': False}
    write('h2-launch-contract.json', h2contract)
    write('h3-launch-contract.json', h3contract)
    write('h2-vs-h3-launch-diff.json', diff)
    write('h3-crashpad-analysis.json', crash)
    print(json.dumps({'result': diff['status'], 'archives_hash_verified': len(PINS), 'probes_started': 0, 'qualification_credit': 0}))


if __name__ == '__main__':
    main()
