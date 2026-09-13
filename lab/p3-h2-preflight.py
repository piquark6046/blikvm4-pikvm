#!/usr/bin/env python3
"""Three-run H2 qualification controller; no reboot/power/flash operation.

Each invocation runs one declared iteration. Any failure freezes the attempt.
Independent VM archive replay is required before the next invocation.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import pwd
import runpy
import shutil
import subprocess
import sys
import tarfile
import time

B = runpy.run_path(str(Path(__file__).with_name('p3-h2-boundary.py')))
require = B['require']
BASE = Path('/var/lib/blikvm-p3-h2')
ATTEMPT = BASE/'attempt'
OLD = Path('/var/lib/blikvm-p3-browser')
PREP = Path('/home/user/blikvm-p3/preparation')
USER = pwd.getpwnam('p3-browser') if os.geteuid() == 0 else None


def paths(root):
    root = Path(root)
    yield root
    if root.is_dir():
        for p in sorted(root.rglob('*')):
            if '__pycache__' not in p.parts:
                yield p


def protected_roots():
    # Include every historical browser test, old evidence, source and private input.
    roots = [OLD/'private', PREP, Path('/home/user/blikvm-p3'),
             Path('/home/user/blikvm-msd/p3-context/lab'),
             Path('/home/user/blikvm-msd/build'), Path('/home/user/blikvm-msd/initramfs'),
             Path('/home/user/blikvm-msd/p3-context/a01-smoke'),
             Path('/home/user/blikvm-msd/private'),
             Path('/home/user/.local/share/blikvm-m7/id_ed25519'),
             Path('/home/user/blikvm-p2/attempt02/coldboot01/known_hosts'), BASE/'lab']
    roots += [p for p in OLD.iterdir() if p.name.startswith(('preflight','permission-test'))]
    return sorted(set(q.resolve(strict=True) for p in roots for q in paths(p)))


def snapshot(inputs):
    result = {}
    for p in inputs:
        m = B['no_acl'](p)
        if p.is_file():
            with p.open('rb') as f:
                m['sha256'] = hashlib.file_digest(f, 'sha256').hexdigest()
        result[str(p)] = m
    return result


def collect(label, dest):
    q = subprocess.run([sys.executable, str(PREP/'collect.py'), str(dest/label)],
                       capture_output=True, text=True, timeout=300)
    B['publish'](dest/(label+'-transport.json'), dict(returncode=q.returncode, stdout=q.stdout, stderr=q.stderr))
    require(q.returncode == 0, 'target inventory transport failed')
    inv = B['read_json'](dest/label/'target.json')
    assess = runpy.run_path(str(PREP/'assess.py'))['assess']
    assess(inv, B['read_json'](PREP/'p2-identity.json'))
    original = B['read_json'](Path('/home/user/blikvm-p3/a01/startup/target.json'))
    for k in ('boot_id', 'sd_cid', 'machine_id', 'host_public_keys', 'hash_checks'):
        require(inv[k] == original[k], 'target continuity failed: '+k)
    def generations(r):
        return [l for key in ('services','ssh_show') for l in r['commands'][key]['stdout'].splitlines()
                if l.startswith(('Id=','InvocationID=','ExecMainStartTimestampMonotonic=','NRestarts='))]
    require(generations(inv) == generations(original), 'target service generation changed')
    return inv


def historical_seal():
    """Preserve additional pre-seal archives without rewriting old failure archives."""
    log = ATTEMPT/'controller/history'
    log.mkdir(mode=0o700)
    roots = [p for p in OLD.iterdir() if p.name.startswith('permission-test')]
    roots += [p for root in OLD.glob('preflight*') for p in root.glob('browser-*') if p.is_dir()]
    # The previous browser home is retired; each new run gets a fresh runtime home.
    roots += [OLD/'home']
    for index, p in enumerate(sorted(roots)):
        r = B['archive_then_seal'](p, ATTEMPT/'archives'/f'historical-{index:03d}.tar.gz',
                                   log/f'{index:03d}-original.json')
        B['publish'](log/f'{index:03d}-sealed.json', r)
    B['publish'](log/'result.json', dict(result='archived_and_sealed', roots=[str(p) for p in roots]))


def archive_iteration(run):
    index = {}
    for p in sorted(run.rglob('*')):
        if p.is_file():
            with p.open('rb') as f:
                index[str(p.relative_to(run))] = hashlib.file_digest(f, 'sha256').hexdigest()
    B['publish'](run/'SHA256.json', index)
    dest = ATTEMPT/'archives'/(run.name+'.tar.gz')
    with tarfile.open(dest, 'x:gz', dereference=False) as t:
        t.add(run, arcname=run.name)
    with dest.open('rb') as f:
        os.fsync(f.fileno())
        digest = hashlib.file_digest(f, 'sha256').hexdigest()
    B['publish'](ATTEMPT/'controller'/(run.name+'-archive.json'), dict(path=str(dest), sha256=digest))
    print(json.dumps(dict(archive=str(dest), sha256=digest)), flush=True)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('iteration', choices=['preflight-001','preflight-002','preflight-003'])
    a = p.parse_args()
    require(os.geteuid() == 0, 'bridge root controller required')
    require(not (ATTEMPT/'controller/FAILED.json').exists(), 'H2 already failed; no retry')
    os.umask(0o077)
    B['browser_idle']()
    n = int(a.iteration[-3:])
    if n > 1:
        for i in range(1,n):
            review = B['read_json'](ATTEMPT/'controller'/f'preflight-{i:03d}-vm-replay.json')
            require(review['result'] == 'P3_H2_ITERATION_PASS', 'prior independent replay missing')
    run = ATTEMPT/a.iteration
    run.mkdir(mode=0o755)
    run.chmod(0o755)
    controller = run/'controller'
    controller.mkdir(mode=0o700)
    r = dict(scope='P3-H2', qualification_credit=0, accepted_cycles=0, reboots=0,
             target_repair=False, result='in_progress', stages=[], started_ns=time.time_ns())
    B['publish'](controller/'start.json', r)
    sources = controller/'sources'
    sources.mkdir(mode=0o700)
    for source in list(BASE.glob('p3-h2-*.py')) + list((BASE/'lab').glob('*browser*')) + [BASE/'lab/msd-hil.py']:
        if source.is_file():
            shutil.copyfile(source, sources/source.name)
    active = None
    try:
        if n == 1:
            historical_seal()
        inputs = protected_roots()
        before_inputs = snapshot(inputs)
        B['publish'](controller/'protected-before.json', before_inputs)
        before = collect('before', controller)
        B['publish'](run/'boot-result.json', dict(run_directory='/home/user/blikvm-p2/attempt02/coldboot01',
                     boot_id=before['boot_id'], qualification_pass=False))
        for label, script in [('msd','msd-browser-hil.py'),('hid','hid-browser-hil.py')]:
            B['browser_idle']()
            active = run/('browser-'+label)
            active.mkdir(mode=0o700)
            home = active/'runtime-home'
            (home/'.pki').mkdir(parents=True, mode=0o700)
            shutil.copytree(OLD/'home/.pki/nssdb', home/'.pki/nssdb')
            for q in [active, *active.rglob('*')]:
                os.chown(q, USER.pw_uid, USER.pw_gid)
                q.chmod(0o700 if q.is_dir() else 0o600)
            control = run/('control-'+label)
            control.mkdir(mode=0o755)
            control.chmod(0o755)
            B['publish'](control/'boundary-canary.json', {'controller':'protected'}, 0o644)
            # All older leaf files and directories are tested again on every launch.
            older = [q for q in ATTEMPT.glob('preflight-*/browser-*') if q != active]
            roots = inputs + [ATTEMPT, BASE, run, controller, control, control/'boundary-canary.json',
                              run/'boot-result.json', ATTEMPT/'controller', ATTEMPT/'archives']
            roots += [q for root in older for q in paths(root)]
            roots += [q for root in ATTEMPT.glob('preflight-*/control-*') for q in paths(root)]
            # Ancestors must not enable arbitrary namespace substitution either.
            roots += list(set(p for q in roots for p in Path(q).parents))
            roots = sorted(set(roots))
            reads = [OLD/'private/ca.crt', OLD/'private/credentials.json', control/'boundary-canary.json',
                     BASE/'lab'/script.replace('-hil.py','.mjs')]
            B['audit'](active, roots, reads, controller/(label+'-before-boundary.json'),
                       traverse=[ATTEMPT,run,control])
            env = dict(os.environ, P3_BROWSER_LEAF=str(active), P3_CONTROL=str(control),
                       HOME=str(home), PYTHONDONTWRITEBYTECODE='1')
            with (control/'harness.log').open('x') as log:
                q = subprocess.run([sys.executable,'lab/'+script,'--output',str(control),
                                    '--boot-result',str(run/'boot-result.json')], cwd=BASE,
                                   env=env, stdout=log, stderr=subprocess.STDOUT, timeout=850, umask=0o022)
            B['browser_idle']()
            result = B['read_json'](control/'result.json')
            r['stages'].append(dict(name=label, returncode=q.returncode, result=result['result']))
            seal = B['archive_then_seal'](active, controller/(label+'-original.tar.gz'),
                                          controller/(label+'-original-metadata.json'))
            B['publish'](controller/(label+'-seal.json'), seal)
            B['audit'](None, roots + list(paths(active)), reads,
                       controller/(label+'-after-boundary.json'))
            active = None
            require(q.returncode == 0 and result['result'] == 'passed' and
                    result['browser']['result'] == 'passed', label+' functional smoke failed')
            require(snapshot(inputs) == before_inputs, 'protected input bytes or metadata changed')
        after = collect('after', controller)
        B['publish'](controller/'protected-after.json', snapshot(inputs))
        require(snapshot(inputs) == before_inputs, 'protected inputs changed')
        r.update(result='completed_pending_independent_replay', target_hashes_matched=10690,
                 boot_id=after['boot_id'], browser_processes=B['browser_idle']())
    except BaseException as e:
        r.update(result='FAILED', error=repr(e))
        B['publish'](ATTEMPT/'controller/FAILED.json', r)
        # Do not repair/retry a failed gate. Preserve and retire any active output.
        try:
            if active is not None and active.exists():
                B['browser_idle']()
                seal = B['archive_then_seal'](active, controller/'failure-original.tar.gz',
                                              controller/'failure-original-metadata.json')
                B['publish'](controller/'failure-seal.json', seal)
            collect('failure-preservation', controller)
        except BaseException as more:
            r['preservation_error'] = repr(more)
        raise
    finally:
        r['finished_ns'] = time.time_ns()
        B['publish'](controller/'result.json', r)
        archive_iteration(run)


if __name__ == '__main__':
    main()
