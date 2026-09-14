#!/usr/bin/env python3
"""Execute the real cycle functions with external actions replaced by fixtures.

No controller module initialization, target connection, process launch or UART
access is allowed. Uses the unchanged production exclusive publisher on disk.
"""
import ast
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import runpy
import socket
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace
from unittest.mock import patch
import uuid

ROOT = Path(__file__).resolve().parents[1]
OLD = ROOT/'lab/p3-a02-cycle01.py'
OLD_SHA256 = 'cebd49d48d27836cbf0f6fd8e25b6b4fed48cbdea35b17fd3c51871cb2090cca'
NEW = ROOT/'lab/p3-a03-cycle01.py'
BOUNDARY = runpy.run_path(str(ROOT/'lab/p3-h2-boundary.py'))
CASES = ('success', 'pre-reboot', 'reboot-request', 'startup-recovery',
         'firmware-chain', 'msd', 'hid', 'seal', 'cycle-final.json', 'result.json',
         'hid+seal', 'result.json-after-write')


def source_sites(source):
    """List every call; reject repeated statically resolvable destinations."""
    tree = ast.parse(source.read_text())
    sites = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'publish':
            sites.append({'line': node.lineno, 'destination': ast.unparse(node.args[0])})
    constants = [s['destination'] for s in sites
                 if s['destination'].startswith("D / '") and s['destination'].endswith("'")]
    assert len(constants) == len(set(constants)), 'duplicate constant publication sites'
    for name in ('cycle.json', 'cycle-final.json', 'result.json'):
        assert sum(s['destination'] == f"D / '{name}'" for s in sites) == 1, name
    assert sum(s['destination'] == 'FAIL' for s in sites) == 1
    return sites


def load_functions(source, namespace):
    tree = ast.parse(source.read_text())
    tree.body = [n for n in tree.body if isinstance(n, ast.FunctionDef)]
    exec(compile(tree, str(source), 'exec'), namespace)


class Ledger:
    def __init__(self, root, fault):
        self.root, self.fault = root, fault
        self.paths, self.originals = [], {}

    def unchanged(self):
        for path, content in self.originals.items():
            assert path.read_bytes() == content, f'published bytes changed: {path}'

    def publish(self, path, value, mode=0o600):
        path = Path(path)
        self.unchanged()
        self.paths.append(str(path.relative_to(self.root)))
        terminal = path.parent.name == 'p3-a03-cycle-001'
        if terminal and path.name == self.fault:
            raise OSError('injected publication failure before exclusive open')
        BOUNDARY['publish'](path, value, mode)
        self.originals.setdefault(path, path.read_bytes())
        self.unchanged()
        if terminal and self.fault == path.name+'-after-write':
            raise OSError('injected failure after exclusive write')


def exercise(root, case, source=NEW):
    root = Path(root).resolve()
    root.mkdir(mode=0o700)
    old = source == OLD
    if old: assert hashlib.sha256(source.read_bytes()).hexdigest() == OLD_SHA256
    attempt = '02' if old else '03'
    name = f'p3-a{attempt}-cycle-001'
    d = root/'controller'/name
    for p in (d/'uart', root/'active', root/'home', root/'input/acks', root/'context', root/'prep'):
        p.mkdir(parents=True, mode=0o700)
    def fixture(path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('x') as f:
            json.dump(value, f)
    fixture(d/'source-provenance.json', {'files': {}, 'clean': True, 'commit': 'f'*40, 'origin_main': 'f'*40})
    fixture(root/'input/contract.json', {'uid': os.getuid(), 'gid': os.getgid()})
    fixture(root/'controller/functional-input-manifest.json', {})
    def inv(boot):
        return dict(boot_id=boot, sd_cid='fixture', machine_id='fixture', host_public_keys={}, hash_checks={},
                    commands={'services': {'stdout': 'Id=fixture'}, 'ssh_show': {'stdout': 'NRestarts=0'}})
    fixture(root/f'controller/p3-a{attempt}-immediate/inventory/target.json', inv('old-boot'))
    fixture(root/'prep/p2-identity.json', {})
    fixture(d/'uart/ready.json', {'pid': os.getpid()})
    (d/'uart/events.jsonl').write_text('{"event":"uart_open"}\n')
    markers = ['U-Boot SPL','BL31:','U-Boot 2021','/boot/boot.scr','Starting kernel',
               'root=PARTUUID=b14b0001-01','systemd[1]']
    (d/'uart/uart-001.raw').write_text(' '.join(markers) if case != 'firmware-chain' else 'missing firmware')
    for directory in [root, *root.rglob('*')]:
        if directory.is_dir(): directory.chmod(0o700)
    ledger = Ledger(root, case)
    calls = []
    def external(label):
        calls.append(label)
        ledger.unchanged()
        if case == label or (case == 'hid+seal' and label == 'seal'):
            raise RuntimeError('injected '+label)
    def seal(*args):
        external('seal')
        return {'fixture': True}
    def audit(leaf, dest):
        ledger.publish(dest, {'fixture': True})
        return {'fixture': True}
    def run(args, **kwargs):
        if args[0] == 'python3' and args[1] == str(root/'prep/collect.py'):
            dest = Path(args[2]); label = dest.name
            external('pre-reboot' if label == 'preboot' else label)
            fixture(dest/'target.json', inv('old-boot' if label in ('preboot', 'failure-preservation') else 'new-boot'))
            return SimpleNamespace(returncode=0, stdout='', stderr='')
        if args[0] == 'fixture-ssh':
            if kwargs.get('input') == 'fixture-msd-query':
                boot = 'new-boot' if 'reboot-command-fixture' in calls and case != 'reboot-request' else 'old-boot'
                state = dict(attrs={}, boot_id=boot, api_returncode=0, api={'result': {'drive': {'connected': True}}})
                return SimpleNamespace(returncode=0, stdout=json.dumps(state), stderr='')
            if 'input' in kwargs:
                calls.append('reboot-command-fixture')
                return SimpleNamespace(returncode=1 if case == 'reboot-request' else 0, stdout='', stderr='')
            external('startup-recovery')
            return SimpleNamespace(returncode=0, stdout='new-boot', stderr='')
        assert args[0] == '/usr/bin/python3' and args[1].endswith('-browser-hil.py'), args
        label = Path(args[1]).name.split('-')[0]
        calls.append(label+'-browser-fixture')
        env = kwargs['env']; output = Path(env['P3_BROWSER_LEAF']); control = Path(args[args.index('--output')+1])
        status = 'failed' if case == label or (case == 'hid+seal' and label == 'hid') else 'passed'
        fixture(control/'result.json', {'result': status})
        fixture(output/'browser-result.json', {'result': status})
        count = 2 if label == 'msd' else 1
        (control/'browser.log').write_text('<launching> fixture\n'*count)
        for i in range(count):
            fixture(output/f'launch-{i}-contract.json', {'fixture': True})
        return SimpleNamespace(returncode=1 if status == 'failed' else 0)
    class TLS:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def wrap_socket(self, *args, **kwargs): return self
        def getpeercert(self, **kwargs): return b'fixture-cert'
        def sendall(self, data): pass
        def recv(self, size): return b'HTTP/1.1 302 Found'
    tick = 0
    def monotonic():
        nonlocal tick
        tick += 61 if case == 'startup-recovery' else 0.01
        return tick
    p = {'mkdir': lambda path, mode=0o700, owner=None: path.mkdir(mode=mode),
         'idle': lambda: {'fixture': True}, 'protected': lambda: {}, 'audit': audit,
         'reset_home': lambda: None, 'manifest': lambda path: {}, 'HOME': root/'home'}
    g = dict(Path=Path, B=root, D=d, NAME=name, FAIL=root/f'controller/P3_A{attempt}_FAILED.json',
             CTX=root/'context', PREP=root/'prep', SSH=['fixture-ssh'], P=p, H={'seal': seal},
             S={'TARGET': 'fixture-msd-query', 'ATTRS': {}, 'check': lambda *a, **k: {'fixture': True}},
             G={'wait_device': lambda *a: 'fixture-device', 'block_identity': lambda *a: {'node': 'fixture-node'},
                'read_image_direct': lambda *a: b'fixture-medium'},
             runpy=SimpleNamespace(run_path=lambda _: {'assess': lambda *a: None}),
             require=BOUNDARY['require'], publish=ledger.publish, read=BOUNDARY['read_json'],
             json=json, hashlib=hashlib, uuid=uuid,
             time=SimpleNamespace(time_ns=time.time_ns, monotonic_ns=time.monotonic_ns,
                                  monotonic=monotonic, sleep=lambda _: None),
             os=SimpleNamespace(kill=lambda *_: None, rename=os.rename),
             subprocess=SimpleNamespace(run=run, DEVNULL=-3, STDOUT=-2),
             socket=SimpleNamespace(create_connection=lambda *a, **k: TLS()),
             ssl=SimpleNamespace(create_default_context=lambda **k: TLS()))
    load_functions(source, g)
    g.update(prerequisite=lambda: None)
    original_read_text = Path.read_text
    def read_text(path, *args, **kwargs):
        if str(path) == '/sys/class/net/enp1s0/carrier': return '1'
        return original_read_text(path, *args, **kwargs)
    error = None
    with patch.object(Path, 'read_text', read_text), contextlib.redirect_stdout(io.StringIO()), \
         patch.object(subprocess, 'run', side_effect=AssertionError('real process forbidden')), \
         patch.object(socket, 'socket', side_effect=AssertionError('real socket forbidden')):
        try: g['execute']()
        except BaseException as ex: error = repr(ex)
    ledger.unchanged()
    report = {'case': case, 'paths': ledger.paths, 'calls': calls, 'error': error,
              'original_bytes_unchanged': True, 'qualification_credit': 0,
              'published_sha256': {str(p.relative_to(root)): hashlib.sha256(b).hexdigest()
                                   for p, b in ledger.originals.items()}}
    fixture(root/'ledger.json', report)
    return report


def check_report(report, old=False):
    paths = report['paths']
    if old:
        assert paths.count('controller/p3-a02-cycle-001/cycle.json') == 3
        assert 'reboot-command-fixture' not in report['calls']
        assert 'FileExistsError' in report['error']
        return
    assert len(paths) == len(set(paths)), paths
    assert sum(p.endswith('/P3_A03_FAILED.json') for p in paths) == (report['case'] != 'success')
    assert (report['error'] is None) == (report['case'] == 'success')
    assert report['original_bytes_unchanged']
    calls = report['calls']; case = report['case']
    assert ('reboot-command-fixture' in calls) == (case != 'pre-reboot')
    if case in ('success', 'hid', 'seal', 'cycle-final.json', 'result.json', 'hid+seal', 'result.json-after-write'):
        assert 'msd-browser-fixture' in calls and 'hid-browser-fixture' in calls and 'seal' in calls
    if case in ('pre-reboot', 'reboot-request', 'startup-recovery', 'firmware-chain'):
        assert 'msd-browser-fixture' not in calls and 'hid-browser-fixture' not in calls
    if case == 'msd': assert 'msd-browser-fixture' in calls and 'hid-browser-fixture' not in calls


def main(dest):
    dest = Path(dest).resolve(); dest.mkdir(mode=0o700)
    sites = source_sites(NEW)
    for case in CASES:
        check_report(exercise(dest/case, case))
    check_report(exercise(dest/'frozen-old', 'success', OLD), old=True)
    summary = {'result': 'PUBLICATION_REHEARSAL_PASS', 'cases': list(CASES),
               'old_bug_reproduced': True, 'publication_sites': sites,
               'qualification_credit': 0, 'target_contact': False, 'browser_launches': 0,
               'source_sha256': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                                 for p in (OLD, NEW, Path(__file__), ROOT/'lab/p3-h2-boundary.py')}}
    BOUNDARY['publish'](dest/'summary.json', summary)
    print(json.dumps(summary, indent=2))


if __name__ == '__main__': main(sys.argv[1])
