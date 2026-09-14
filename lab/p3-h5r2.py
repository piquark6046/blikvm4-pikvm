#!/usr/bin/env python3
"""Prospective bridge-only H5R2 preparation/minimal controller. Never contacts target.

H3 helpers are reused without changing historical sources or namespaces.
All failed runs latch permanently; subsequent commands refuse qualification.
"""
import errno
import hashlib
import json
import os
from pathlib import Path
import pwd
import runpy
import shutil
import stat
import subprocess
import sys
import time
import uuid

BASE = Path('/var/lib/blikvm-p3-h5r2')
HOME = BASE/'home'
USER = 'p3-browser-h5r2'
HERE = Path(__file__).resolve().parent
H = runpy.run_path(str(HERE/'p3-h3-boundary.py'))
require, publish, read = H['require'], H['publish'], H['read_json']
N = runpy.run_path(str(HERE/'p3-h5r1-netns.py'))
RUNTIME = BASE/'input/runtime'
CHROME = RUNTIME/'browsers/chromium-1208/chrome-linux64/chrome'
PW = RUNTIME/'node_modules/playwright'


def command(args, **kwargs):
    return subprocess.run(args, check=True, capture_output=True, text=True, **kwargs).stdout


def idle():
    uid = pwd.getpwnam(USER).pw_uid
    found = []
    for p in Path('/proc').glob('[0-9]*/status'):
        try:
            fields = dict(s.split(':', 1) for s in p.read_text().splitlines() if ':' in s)
            if uid in map(int, fields['Uid'].split()):
                found.append(p.parent.name)
        except FileNotFoundError:
            pass
    require(not found, 'H5R2 UID processes remain: '+repr(found))
    return {'uid': uid, 'pids': found, 'checked_ns': time.time_ns()}


# Archive/seal retain H3's tested whole-leaf rename architecture, using H5R2 UID.
for name in ('archive', 'seal'):
    H[name].__globals__['browser_idle'] = idle


def manifest(root):
    result = {}
    root = Path(root)
    for p in [root, *sorted(root.rglob('*'))]:
        if root == BASE/'input' and (p == root/'acks' or root/'acks' in p.parents):
            continue  # Separately audited, root-owned live controller protocol.
        m = H['metadata'](p)
        require(m['type'] in (stat.S_IFDIR, stat.S_IFREG, stat.S_IFLNK), 'special input')
        if p.is_file() and not p.is_symlink():
            m['sha256'] = H['digest'](p)
        result[str(p.relative_to(root))] = m
    return result


def runtime_identity(tree):
    # Copy-local inode/device/ctime and directory allocation are not identities.
    return {name: {k:v for k,v in m.items() if k not in ('dev','ino','ctime_ns')
                   and not (m['type'] == stat.S_IFDIR and k in ('size','nlink'))}
            for name,m in tree.items()}


def ancestors(paths):
    return {str(q): H['metadata'](q) for p in paths for q in [Path(p), *Path(p).parents]}


def mkdir(p, mode=0o700, owner=None):
    p.mkdir(mode=mode)
    p.chmod(mode)
    if owner:
        os.chown(p, *owner)


def reset_home():
    require(not list(HOME.iterdir()), 'home must be empty before clean runtime preparation')
    u = pwd.getpwnam(USER)
    mkdir(HOME/'.pki', owner=(u.pw_uid, u.pw_gid))
    shutil.copytree(BASE/'input/nssdb', HOME/'.pki/nssdb')
    for p in (HOME/'.pki').rglob('*'):
        os.chown(p, u.pw_uid, u.pw_gid)
        p.chmod(0o700 if p.is_dir() else 0o600)


def source_check():
    source = read(HERE/'source-provenance.json')
    require(source['clean'] is True and source['commit'] == source['origin_main'], 'source not pushed clean')
    require(len(source['commit']) == 40, 'invalid source commit')
    for name, digest in source['files'].items():
        require(Path(name).name == name, 'invalid source filename')
        require(H['digest'](HERE/name) == digest, 'deployed source differs: '+name)
    return source


def prepare():
    source = source_check()
    require(not BASE.exists(), 'H5R2 namespace exists; no destructive reprepare')
    try:
        pwd.getpwnam(USER)
    except KeyError:
        pass
    else:
        raise RuntimeError('H5R2 account already exists')
    mkdir(BASE, 0o755)
    for name, mode in [('controller', 0o700), ('input', 0o755), ('active', 0o711), ('sealed', 0o700)]:
        mkdir(BASE/name, mode)
    mkdir(BASE/'input/acks', 0o755)
    publish(BASE/'controller/source-provenance.json', source)
    command(['useradd', '--system', '--user-group', '--no-create-home', '--home-dir', str(HOME),
             '--shell', '/usr/sbin/nologin', USER])
    u = pwd.getpwnam(USER)
    require(command(['id', '-G', USER]).strip() == str(u.pw_gid), 'supplementary group')
    require(command(['passwd', '-S', USER]).split()[1] == 'L', 'account not locked')
    mkdir(HOME, owner=(u.pw_uid, u.pw_gid))
    runtime_source = Path('/var/lib/blikvm-p3-h3/input/context/out/kvmd-web/browser')
    # This root-owned source has a complete historical manifest. Preserve its
    # metadata verbatim; no distribution-wide chmod or old runtime-home reuse.
    command(['cp', '-a', '--', str(runtime_source), str(RUNTIME)])
    for p in [RUNTIME, *RUNTIME.rglob('*')]:
        m = H['no_acl'](p)
        require(m['uid'] == 0 and not m['mode'] & 0o022, 'runtime not immutable to H5R2 UID')
    ca = BASE/'input/ca.crt'
    shutil.copyfile('/var/lib/blikvm-p3-h3/input/context/private/ca.crt', ca)
    ca.chmod(0o644)
    mkdir(BASE/'input/nssdb', 0o755)
    db = 'sql:'+str(BASE/'input/nssdb')
    command(['/usr/bin/certutil', '-N', '-d', db, '--empty-password'])
    command(['/usr/bin/certutil', '-A', '-d', db, '-n', 'H5R2 enrolled public CA', '-t', 'C,,', '-i', str(ca)])
    certs = command(['/usr/bin/certutil', '-L', '-d', db])
    keys = subprocess.run(['/usr/bin/certutil', '-K', '-d', db], capture_output=True, text=True)
    require('H5R2 enrolled public CA' in certs and 'no keys found' in keys.stdout+keys.stderr, 'NSS public-only check failed')
    for p in (BASE/'input/nssdb').iterdir():
        p.chmod(0o644)
    for name in source['files']:
        shutil.copyfile(HERE/name, BASE/'input'/name)
        (BASE/'input'/name).chmod(0o644)
    publish(BASE/'input/source-provenance.json', source, 0o644)
    files = {}
    for p in ['/usr/bin/node', '/usr/bin/xvfb-run', '/usr/bin/Xvfb', '/usr/bin/certutil', '/usr/bin/xauth', '/usr/bin/unshare', '/usr/sbin/ip', '/usr/bin/python3']:
        real = Path(p).resolve(strict=True)
        files[p] = {'realpath': str(real), 'sha256': H['digest'](real), 'metadata': H['metadata'](real)}
    env = {'HOME': str(HOME), 'PATH': '/usr/bin:/bin', 'PLAYWRIGHT_BROWSERS_PATH': str(RUNTIME/'browsers'),
           'PLAYWRIGHT_HOST_PLATFORM_OVERRIDE': 'ubuntu24.04-x64', 'DEBUG': 'pw:browser*', 'LANG': 'C.UTF-8'}
    contract = {'scope': 'P3-H5R2 prospective runtime', 'uid': u.pw_uid, 'gid': u.pw_gid, 'groups': [u.pw_gid],
                'passwd': command(['getent', 'passwd', USER]).strip(), 'account_status': command(['passwd', '-S', USER]).strip(),
                'home': str(HOME), 'shell': u.pw_shell, 'environment': env, 'cwd': str(BASE/'input'),
                'executables': files, 'node_version': command(['/usr/bin/node', '--version']).strip(),
                'package_versions': command(['dpkg-query', '-W', 'nodejs', 'xvfb', 'libnss3-tools', 'xauth', 'util-linux']),
                'playwright': str(PW), 'playwright_version': read(PW/'package.json')['version'],
                'playwright_sha256': H['digest'](PW/'package.json'), 'chromium': str(CHROME),
                'chromium_sha256': H['digest'](CHROME), 'chromium_version': read(Path('/var/lib/blikvm-p3-h5/input/contract.json'))['chromium_version'],
                'chromium_version_source': 'H5 frozen version bound to matching binary SHA-256; no pre-selftest execution',
                'runtime_manifest': manifest(RUNTIME), 'nss_manifest': manifest(BASE/'input/nssdb'),
                'nss_certificates': certs, 'nss_keys': keys.stdout+keys.stderr, 'launch_options': {'headless': False},
                'xvfb_arguments': ['-a', '-s', '-screen 0 1600x1200x24 -nolisten tcp'],
                'isolation': 'unshare --net; loopback only; no host network sockets inherited',
                'ancestors': ancestors([HOME, BASE/'controller', BASE/'input', BASE/'sealed', RUNTIME, *files]),
                'target_contacted': False, 'qualification_credit': 0}
    historical = read(Path('/var/lib/blikvm-p3-h5/input/contract.json'))
    for key in ('chromium_sha256', 'playwright_sha256', 'playwright_version'):
        require(contract[key] == historical[key], 'frozen H5 runtime identity differs: '+key)
    require(runtime_identity(contract['runtime_manifest']) == runtime_identity(historical['runtime_manifest']), 'frozen H5 runtime tree differs')
    qualified = read(Path('/var/lib/blikvm-p3-h5r1/input/contract.json'))
    require(read(Path('/var/lib/blikvm-p3-s0/vm-current-replay.json'))['result']=='S0_CURRENT_EMPTY_VERIFIED','S0 preservation missing')
    require(read(HERE/'s0-acceptance.json')['result']=='P3_S0_CLEAN_BOOT_INVARIANT_PASS','S0 acceptance missing')
    for key in ('chromium_sha256','playwright_sha256','playwright_version','launch_options','xvfb_arguments'):
        require(contract[key]==qualified[key],'H5R1 inheritance drift: '+key)
    for name in ('/usr/bin/node','/usr/bin/xvfb-run','/usr/bin/Xvfb','/usr/bin/xauth'):
        require(contract['executables'][name]['sha256']==qualified['executables'][name]['sha256'],'executable inheritance drift')
    require(runtime_identity(contract['runtime_manifest'])==runtime_identity(qualified['runtime_manifest']),'runtime inheritance drift')
    for name in ('p3-h5r1-netns.py','p3-h5r1-netns.cjs','p3-h3-boundary.py'):
        require(H['digest'](HERE/name)==H['digest'](Path('/var/lib/blikvm-p3-h5r1/input')/name),'isolation inheritance drift')
    publish(BASE/'controller/h5r1-inheritance.json',{'result':'FROZEN_RUNTIME_AND_ISOLATION_MATCH','minimal_launches_required':1,'qualified_contract_sha256':H['digest'](Path('/var/lib/blikvm-p3-h5r1/input/contract.json')),'target_contacted':False})
    contract['source_commit'] = source['commit']
    publish(BASE/'input/contract.json', contract, 0o644)
    config = read(Path('/var/lib/blikvm-p3-h3/controller/config.json'))
    config['protected_roots'] += ['/var/lib/blikvm-p3-h5r1', '/home/user/blikvm-p3-h5r1-exports', '/var/lib/blikvm-p3-s0', '/home/user/blikvm-p3-s0-exports', '/var/lib/blikvm-p3-h5', '/home/user/blikvm-p3-h5-exports', '/var/lib/blikvm-p3-h3', '/home/user/blikvm-p3-h3-exports', '/home/user/blikvm-p3-h4-exports']
    config['protected_roots'] = list(dict.fromkeys(config['protected_roots']))
    publish(BASE/'controller/config.json', config)
    publish(BASE/'controller/input-manifest.json', manifest(BASE/'input'))
    publish(BASE/'controller/prepared.json', {'account': contract['passwd'], 'target_contacted': False, 'qualification_credit': 0})


def payload(leaf):
    config = read(BASE/'controller/config.json')
    roots = [BASE/n for n in ('input', 'active', 'sealed', 'controller')]
    roots += [Path(config['legacy']), *map(Path, config['protected_roots'])]
    barriers = [BASE/'controller', BASE/'sealed', Path(config['legacy'])]
    barriers += list((BASE/'sealed').iterdir())
    parents = ancestors([BASE, *roots])
    return {'active': str(leaf) if leaf else None, 'roots': list(map(str, roots)),
            'barriers': list(map(str, barriers)), 'reads': [str(BASE/'input/ca.crt'), str(CHROME), str(PW/'package.json')],
            'traverse': [str(BASE), str(BASE/'active'), str(HOME)], 'protected_dirs': list(parents),
            'protected_files': config['protected_files']}, parents


def audit(leaf, destination):
    idle()
    require(list((BASE/'active').iterdir()) == ([leaf] if leaf else []), 'extra active leaf')
    requirements, parents = payload(leaf)
    p = subprocess.run(['runuser', '-u', USER, '--', '/usr/bin/python3', str(BASE/'input/p3-h5r2.py'), 'worker'],
                       input=json.dumps(requirements), capture_output=True, text=True)
    result = {'requirements': requirements, 'ancestors': parents, 'returncode': p.returncode,
              'effective': json.loads(p.stdout), 'stderr': p.stderr, 'checked_ns': time.time_ns()}
    publish(destination, result)
    require(p.returncode == 0, 'global actual-UID permission audit failed')
    c = read(BASE/'input/contract.json')
    e = result['effective']
    require((e['uid'], e['gid'], e['groups']) == (c['uid'], c['gid'], c['groups']), 'audit identity drift')
    return requirements


def protected():
    config = read(BASE/'controller/config.json')
    return {p: manifest(p) for p in [config['legacy'], *config['protected_roots']]}


def isolated(leaf, requirements, mode, host_netns):
    # Exact same namespace/UID mechanism for the self-test and minimal launches.
    c = read(BASE/'input/contract.json')
    observation = N['observe'](host_netns)
    observation.update(uid=c['uid'], gid=c['gid'], groups=c['groups'])
    publish(Path(requirements).with_suffix('.netns.json'), observation, 0o644)
    print(json.dumps({'pre_drop': observation}), flush=True)
    N['validate'](observation)
    os.setgroups(c['groups']); os.setgid(c['gid']); os.setuid(c['uid'])
    os.chdir(c['cwd']); os.umask(0o077)
    env = dict(c['environment'], H5R1_LEAF=leaf, H5R1_REQUIREMENTS=requirements,
               H5R1_NETNS_EXPECTED=json.dumps(observation))
    if mode == 'selftest':
        os.execve('/usr/bin/node', ['/usr/bin/node', str(BASE/'input/p3-h5r1-netns.cjs')], env)
    require(mode == 'minimal', 'unknown isolated mode')
    os.execve('/usr/bin/xvfb-run', ['/usr/bin/xvfb-run', *c['xvfb_arguments'], '/usr/bin/node',
               str(BASE/'input/p3-h5r2-blank.cjs')], env)


def selftest():
    source_check()
    require(not (BASE/'controller/FAILED.json').exists(), 'H5R2 FAILED; no retry')
    idle()
    run = BASE/'controller/netns-selftest'
    mkdir(run)
    r = {'name':'netns-selftest', 'qualification_credit':0, 'target_contacted':False}
    try:
        req = BASE/'input/acks/selftest-requirements.json'
        publish(req, {}, 0o644)
        with (run/'netns.log').open('x') as log:
            p = subprocess.run(['/usr/bin/unshare', '--net', '/usr/bin/python3',
                str(BASE/'input/p3-h5r2.py'), 'isolated', '', str(req), 'selftest',
                os.readlink('/proc/self/ns/net')], stdin=subprocess.DEVNULL,
                stdout=log, stderr=subprocess.STDOUT, close_fds=True, timeout=30)
        r['returncode'] = p.returncode
        r['browser_idle'] = idle()
        require(p.returncode == 0, 'netns-only self-test failed; STOP before Chromium')
        r['result'] = 'NETNS_SELFTEST_PASS'
    except BaseException as e:
        r.update(result='FAILED', error=repr(e))
        publish(BASE/'controller/FAILED.json', r)
    publish(run/'result.json', r)
    print(json.dumps(r), flush=True)
    require(r['result'] != 'FAILED', 'H5R2 stopped before Chromium')


def prior_replay(name):
    r = read(BASE/'controller'/name/'result.json')
    ack = read(BASE/'controller'/(name+'-vm-replay.json'))
    require(ack['result'] == 'H5R2_MINIMAL_ACCEPTED' and ack['name'] == name,
            'independent VM replay missing')
    require(ack['leaf_archive_sha256'] == r['seal']['sha256'], 'replay archive mismatch')


def minimal(number):
    require(number in (1, 2, 3), 'invalid iteration')
    source_check()
    require(not (BASE/'controller/FAILED.json').exists(), 'H5R2 FAILED; no retry')
    require(read(BASE/'controller/netns-selftest/result.json')['result'] == 'NETNS_SELFTEST_PASS', 'netns-only gate missing')
    for i in range(1, number):
        prior_replay(f'minimal-{i:03d}')
    idle()
    name = f'minimal-{number:03d}'
    run = BASE/'controller'/name
    mkdir(run)
    leaf = BASE/'active'/(name+'-'+uuid.uuid4().hex)
    c = read(BASE/'input/contract.json')
    r = {'name': name, 'result': 'in_progress', 'target_contacted': False, 'qualification_credit': 0,
         'accepted_cycles': 0, 'started_ns': time.time_ns(), 'leaf': str(leaf)}
    publish(run/'start.json', r)
    before = None
    try:
        require(not list((BASE/'active').iterdir()), 'another active leaf')
        mkdir(leaf, owner=(c['uid'], c['gid']))
        reset_home()
        require(manifest(BASE/'input') == read(BASE/'controller/input-manifest.json'), 'protected input drift')
        before = protected()
        publish(run/'protected-before.json', before)
        req = audit(leaf, run/'before-audit.json')
        publish(BASE/'input/acks'/(name+'-requirements.json'), req, 0o644)
        # Requirements are controller-owned protocol output, excluded from frozen input manifest.
        with (run/'browser-debug.log').open('x') as log:
            p = subprocess.run(['/usr/bin/unshare', '--net', '/usr/bin/python3', str(BASE/'input/p3-h5r2.py'),
                                'isolated', str(leaf), str(BASE/'input/acks'/(name+'-requirements.json')),
                                'minimal', os.readlink('/proc/self/ns/net')],
                               stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, close_fds=True, timeout=150)
        r['returncode'] = p.returncode
        logtext = (run/'browser-debug.log').read_text()
        r['generated_argv_lines'] = [line for line in logtext.splitlines() if '<launching>' in line]
        publish(run/'generated-argv.json', r['generated_argv_lines'])
        r['browser_idle'] = idle()
        r['browser_result'] = read(leaf/'result.json') if (leaf/'result.json').exists() else None
        require(p.returncode == 0 and r['browser_result']['result'] == 'MINIMAL_BROWSER_PASS', 'minimal browser launch failed')
        require(len(r['generated_argv_lines']) == 1 and 'SIGTRAP' not in logtext, 'missing argv or SIGTRAP')
        require((leaf/'launch-contract.json').is_file(), 'prospective contract missing')
        r['result'] = 'MINIMAL_PASS_PENDING_VM_REPLAY'
    except BaseException as e:
        r.update(result='FAILED', error=repr(e))
        publish(BASE/'controller/FAILED.json', r)
    finally:
        try:
            r['browser_idle_after'] = idle()
            if leaf.exists():
                mkdir(leaf/'runtime-home')
                for p in list(HOME.iterdir()):
                    os.rename(p, leaf/'runtime-home'/p.name)
                # Preserve Crashpad/cache before sealing, including directory metadata.
                r['seal'] = H['seal'](leaf, BASE)
            audit(None, run/'after-seal-audit.json')
            actual = manifest(BASE/'input')
            baseline = read(BASE/'controller/input-manifest.json')
            require(actual == baseline, 'protected inputs changed after launch')
            after = protected()
            publish(run/'protected-after.json', after)
            require(before is not None and after == before, 'historical or original protected inputs changed')
            r['protected_inputs_unchanged'] = True
        except BaseException as e:
            r.update(result='FAILED', preservation_error=repr(e))
            if not (BASE/'controller/FAILED.json').exists():
                publish(BASE/'controller/FAILED.json', r)
        r['finished_ns'] = time.time_ns()
        publish(run/'result.json', r)
    print(json.dumps(r))
    require(r['result'] != 'FAILED', 'H5R2 stopped; no later probe or target contact')


if __name__ == '__main__':
    if sys.argv[1:] == ['worker']:
        H['worker'](json.load(sys.stdin))
    else:
        require(os.geteuid() == 0, 'root controller required')
        os.umask(0o077)
        if sys.argv[1:] == ['prepare']:
            prepare()
        elif sys.argv[1:] == ['selftest']:
            selftest()
        elif sys.argv[1] == 'minimal':
            minimal(int(sys.argv[2]))
        elif sys.argv[1] == 'isolated':
            isolated(*sys.argv[2:])
        else:
            raise SystemExit('prepare | selftest | minimal 1..3 | isolated LEAF REQUIREMENTS | worker')
