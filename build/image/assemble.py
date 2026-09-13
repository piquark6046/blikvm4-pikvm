#!/usr/bin/env python3
"""Assemble frozen P1 inputs into regular files only. Never accepts block devices."""
import argparse
from collections import Counter
import hashlib
import json
import mmap
import os
from pathlib import Path
import re
import shutil
import stat
import struct
import subprocess
import tarfile
import zlib

if not __debug__:
    raise RuntimeError("P1 gates require Python assertions; optimization is forbidden")

REPO = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
OFFSET = 4 * 1024**2
ROOT_SIZE = 1024**3
SIZE = OFFSET + ROOT_SIZE
UUID = 'b14b0001-2026-4001-8001-000000000001'
PARTUUID = 'b14b0001-01'
LABEL = 'blikvm-root'
EPOCH = 1788652800
NETWORK_PATH = 'etc/systemd/network/10-lab.network'
P1_NETWORK = (b'[Match]\nName=eth0\n[Network]\nAddress=192.168.88.2/24\n'
              b'DHCP=no\nLinkLocalAddressing=no\nIPv6AcceptRA=no\nLLMNR=no\n'
              b'MulticastDNS=no\n[Link]\nRequiredForOnline=routable\n')


def standalone_network(root, revision):
    """Reject drift; R1 changes exactly one line in the standalone image only."""
    assert revision in ('p1', 'p2-r1-candidate1')
    path = root/NETWORK_PATH
    assert path.read_bytes() == P1_NETWORK, 'frozen standalone network input drift'
    if revision == 'p2-r1-candidate1':
        path.write_bytes(P1_NETWORK.replace(b'[Network]\n',
                         b'[Network]\nConfigureWithoutCarrier=yes\n'))

ENROLL = {
    'etc/kvmd/htpasswd': (0o400, 988, 0),
    'etc/kvmd/nginx/ssl/server.crt': (0o644, 0, 0),
    'etc/kvmd/nginx/ssl/server.key': (0o600, 0, 0),
    'home/blikvm/.ssh/authorized_keys': (0o600, 1000, 1000),
}


def digest(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def run(args, **kwargs):
    return subprocess.run([str(x) for x in args], check=True, capture_output=True,
                          env={**os.environ, 'LC_ALL': 'C', 'TZ': 'UTC',
                               'SOURCE_DATE_EPOCH': str(EPOCH),
                               'E2FSPROGS_FAKE_TIME': str(EPOCH),
                               'MKE2FS_CONFIG': str(HERE/'mke2fs.conf')}, **kwargs)


def regular(path):
    if not stat.S_ISREG(path.lstat().st_mode):
        raise ValueError(f'not a regular file: {path}')


def inventory(root):
    result = {}
    paths = [root]
    for current, dirs, files in os.walk(root, followlinks=False):
        paths.extend(Path(current)/n for n in dirs + files)
    for p in sorted(set(paths)):
        s = p.lstat()
        item = {'mode': stat.S_IMODE(s.st_mode), 'uid': s.st_uid, 'gid': s.st_gid,
                'mtime': int(s.st_mtime), 'type': stat.S_IFMT(s.st_mode)}
        if p.is_symlink():
            item['target'] = os.readlink(p)
        elif p.is_file():
            item.update(size=s.st_size, sha256=digest(p), nlink=s.st_nlink)
        elif not p.is_dir():
            raise ValueError(f'unexpected special file: {p}')
        result[str(p.relative_to(root))] = item
    return result


def secret_scan(root, image):
    hits = []
    checked = 0
    exceptions = json.loads((HERE/'public-constants.json').read_text())
    accepted = Counter(); raw_constants = Counter()
    # Detect actual serialized material, including unused/raw image areas.
    patterns = [re.compile(rb'-----BEGIN (?:RSA |EC |DSA |OPENSSH |ENCRYPTED )?PRIVATE KEY-----[\r\n]*[A-Za-z0-9+/=\r\n]{32,}'),
                re.compile(rb'\$(?:2[aby]\$[0-9]{2}\$[./A-Za-z0-9]{53}|6\$[./A-Za-z0-9]{1,16}\$[./A-Za-z0-9]{86}|y\$[./A-Za-z0-9]{1,16}\$[./A-Za-z0-9]{1,86}\$[./A-Za-z0-9]{43})')]
    for current, _, names in os.walk(root):
        for name in names:
            p = Path(current)/name
            if p.is_symlink() or not p.is_file():
                continue
            rel = str(p.relative_to(root)); data = p.read_bytes(); checked += 1
            matches = [m.group() for pat in patterns for m in pat.finditer(data)]
            if matches:
                tokens = [hashlib.sha256(b).hexdigest() for b in matches]
                exception = exceptions.get(rel, {})
                if exception.get('file_sha256') == digest(p) and exception.get('token_sha256') == tokens:
                    accepted.update(tokens)
                else:
                    hits.append({'path': rel, 'reason': 'serialized credential'})
            sensitive = (rel.endswith('/authorized_keys') or
                         rel in ('etc/kvmd/htpasswd', 'var/lib/systemd/random-seed') or
                         re.fullmatch(r'etc/ssh/ssh_host_.*_key', rel) or
                         rel.startswith(('root/.ssh/', 'etc/credstore/', 'etc/credstore.encrypted/')))
            if sensitive and data:
                hits.append({'path': rel, 'reason': 'nonempty enrollment/state'})
            if re.search(r'(^|/)(credentials\.json|enrollment\.cpio\.gz|server\.key|ca\.key|id_ed25519|id_rsa|\.bash_history)$', rel):
                hits.append({'path': rel, 'reason': 'private filename'})
            if rel in ('etc/shadow', 'etc/shadow-'):
                if any(line.split(':')[1] not in ('*', '!', '!!', '!*') for line in data.decode().splitlines()):
                    hits.append({'path': rel, 'reason': 'unlocked or password-bearing account'})
    with image.open('rb') as f, mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as data:
        for pat in patterns:
            for match in pat.finditer(data):
                token = hashlib.sha256(match.group()).hexdigest()
                if token in accepted:
                    raw_constants[token] += 1
                else:
                    hits.append({'path': '<raw image>', 'reason': 'serialized credential'})
    if raw_constants != accepted:
        hits.append({'path': '<raw image>', 'reason': 'public constant count differs from reviewed filesystem files'})
    report = {'reviewed_public_constants': dict(accepted), 'exception_file_sha256': digest(HERE/'public-constants.json'), 'result': 'failed' if hits else 'passed', 'regular_files_scanned': checked,
              'raw_bytes_scanned': image.stat().st_size, 'hits': hits,
              'scope': 'all filesystem regular files, credential paths, shadow fields, and all raw image bytes'}
    if hits:
        raise ValueError(json.dumps(report))
    return report


def verify_script(script, command):
    b = script.read_bytes()
    fields = struct.unpack('>7I4B32s', b[:64])
    header = bytearray(b[:64]); struct.pack_into('>I', header, 4, 0)
    assert fields[0] == 0x27051956 and fields[1] == zlib.crc32(header)
    assert fields[2] == EPOCH and fields[3] == len(b)-64
    assert fields[6] == zlib.crc32(b[64:]) and fields[9] == 6 and fields[10] == 0
    assert struct.unpack('>II', b[64:72]) == (len(command.read_bytes()), 0)
    assert b[72:] == command.read_bytes()
    return run(['dumpimage', '-l', script]).stdout.decode()


def check_inputs():
    lock = json.loads((HERE/'inputs.lock.json').read_text())
    assert run(['git', '-C', REPO, 'rev-parse', lock['acceptance_tag']+'^{commit}']).stdout.decode().strip() == lock['acceptance_commit']
    assert digest(REPO/'research/evidence/p1/vendor-layout.json') == lock['vendor_layout_sha256']
    for name, item in lock['inputs'].items():
        p = REPO/item['path']; regular(p)
        assert p.stat().st_size == item['size'] and digest(p) == item['sha256'], name
    for name, h in lock['linux_patch_sha256'].items():
        assert digest(REPO/name) == h, name
    config = (REPO/lock['inputs']['linux.config']['path']).read_text()
    for key in ['MMC', 'MMC_BLOCK', 'MMC_SUNXI', 'MSDOS_PARTITION', 'EXT4_FS', 'DEVTMPFS', 'DEVTMPFS_MOUNT']:
        assert f'CONFIG_{key}=y\n' in config, key
    for key in ['PROC_PAGE_MONITOR', 'SLUB_DEBUG', 'DEBUG_FS', 'FTRACE']:
        assert f'# CONFIG_{key} is not set' in config
    return lock


def mbr():
    b = bytearray(512)
    struct.pack_into('<I', b, 440, 0xb14b0001)
    b[446:462] = struct.pack('<B3sB3sII', 0x80, b'\xfe\xff\xff', 0x83,
                             b'\xfe\xff\xff', OFFSET//512, ROOT_SIZE//512)
    b[510:] = b'\x55\xaa'
    return b


def normalize(fs, root, work):
    commands = []
    names = ['<2>', '<7>', '<8>', '<11>']
    names += ['/' + n if n != '.' else '/' for n in inventory(root)]
    for name in names:
        assert not any(c in name for c in ['"', '\n', '\r'])
        for field in ['atime', 'ctime', 'mtime', 'crtime']:
            commands.append(f'set_inode_field "{name}" {field} @{EPOCH}')
            commands.append(f'set_inode_field "{name}" {field}_extra 0')
        commands.append(f'set_inode_field "{name}" generation 0')
    commands += [f'set_super_value {f} @{EPOCH}' for f in ['mtime', 'wtime', 'lastcheck', 'mkfs_time']]
    commands.append('set_super_value kbytes_written 0')
    batch = work/'normalize.debugfs'; batch.write_text('\n'.join(commands)+'\n')
    p = run(['debugfs', '-w', '-f', batch, fs]); (work/'normalize.log').write_bytes(p.stdout+p.stderr)
    errors = p.stderr.decode().splitlines()[1:]
    assert not errors, errors[:10]


def validate(image, work, expected, lock, vendor, enrolled=False):
    before = digest(image)
    with image.open('rb') as f:
        assert f.read(512) == mbr()
        for x in vendor['bootloader_extents']:
            f.seek(x['offset']); b = f.read(x['size'])
            assert hashlib.sha256(b).hexdigest() == x['sha256']
        # Every other pre-root byte must be zero, not stale partition data.
        f.seek(0); prefix = bytearray(f.read(OFFSET)); prefix[:512] = bytes(512)
        for x in vendor['bootloader_extents']:
            prefix[x['offset']:x['offset']+x['size']] = bytes(x['size'])
        assert not any(prefix)
        f.seek(OFFSET)
        fs = work/'validation.ext4'
        with fs.open('xb') as out:
            shutil.copyfileobj(f, out, 1024**2)
    regular(fs)
    p = run(['e2fsck', '-fn', fs]); (work/'e2fsck.log').write_bytes(p.stdout+p.stderr)
    table = json.loads(run(['sfdisk', '--json', image]).stdout)['partitiontable']
    assert table['label'] == 'dos' and table['id'] == '0xb14b0001' and len(table['partitions']) == 1
    part = table['partitions'][0]
    assert (part['start'], part['size'], part['type'], part['bootable']) == (8192, 2097152, '83', True)
    # Only the newly created regular validation file is attached; always RO.
    loop = run(['losetup', '--find', '--show', '--read-only', fs]).stdout.decode().strip()
    mount = work/'mount'; mount.mkdir()
    mounted = False
    try:
        run(['mount', '-t', 'ext4', '-o', 'ro,noload', loop, mount]); mounted = True
        actual = inventory(mount)
        assert actual == expected, [n for n in set(actual)|set(expected) if actual.get(n) != expected.get(n)][:20]
        for n, item in lock['contracts'].items():
            assert digest(mount/n) == item['sha256'], n
        for n in ['Image', 'sun50i-h616-blikvm-v4.dtb']:
            assert digest(mount/'boot'/n) == lock['inputs'][n]['sha256']
        assert (mount/'boot/boot.cmd').read_bytes() == (HERE/'boot.cmd').read_bytes()
        script = verify_script(mount/'boot/boot.scr', HERE/'boot.cmd')
        (work/'boot-script-validation.txt').write_text(script)
        identity = run(['blkid', '-p', '-o', 'export', fs]).stdout.decode()
        assert f'UUID={UUID}\n' in identity and f'LABEL={LABEL}\n' in identity
        assert (mount/'etc/fstab').read_text() == f'PARTUUID={PARTUUID} / ext4 defaults 0 1\n'
        scan = {'result': 'private enrollment; not a public artifact'} if enrolled else secret_scan(mount, image)
        assert not list(mount.glob('**/*taildiag*'))
        assert not (mount/'sys/kernel/debug').is_mount()
        save(work/'secret-scan.json', scan)
    finally:
        if mounted:
            run(['umount', mount])
        run(['losetup', '-d', loop])
    assert digest(image) == before
    fs.unlink()
    return {'result': 'passed', 'image_sha256_before_after': before, 'e2fsck_exit': 0,
            'filesystem_entries_verified': len(expected), 'read_only_loop_mount': True,
            'root_uuid': UUID, 'root_label': LABEL, 'script_crc_verified': True, 'secret_scan': scan}


def assemble(destination, vendor_dir, revision='p1'):
    if os.geteuid() != 0:
        raise ValueError('run as root to preserve numeric owners and use read-only loop validation')
    lock = check_inputs()
    dest = destination.resolve()
    assert dest.is_relative_to(REPO/'out') and not dest.exists(), 'new clean output below repository out/ required'
    dest.mkdir(parents=True, mode=0o755)
    work = dest/'work'; work.mkdir(); root = work/'root'; root.mkdir()
    vendor = json.loads((REPO/'research/evidence/p1/vendor-layout.json').read_text())
    for x in vendor['bootloader_extents']:
        p = vendor_dir/x['name']; regular(p)
        assert p.stat().st_size == x['size'] and digest(p) == x['sha256']
    archive = REPO/lock['inputs']['rootfs.tar.gz']['path']
    with tarfile.open(archive) as t:
        # The complete immutable archive hash above is the trust boundary.
        t.extractall(root, filter='fully_trusted')
    original = inventory(root)
    for name, item in lock['contracts'].items():
        assert digest(root/name) == item['sha256']
    for name in ['Image', 'sun50i-h616-blikvm-v4.dtb']:
        shutil.copyfile(REPO/lock['inputs'][name]['path'], root/'boot'/name)
    shutil.copyfile(HERE/'boot.cmd', root/'boot/boot.cmd')
    run(['mkimage', '-A', 'arm', '-O', 'linux', '-T', 'script', '-C', 'none', '-n', 'BliKVM standalone SD', '-d', root/'boot/boot.cmd', root/'boot/boot.scr'])
    verify_script(root/'boot/boot.scr', HERE/'boot.cmd')
    (root/'etc/fstab').write_text(f'PARTUUID={PARTUUID} / ext4 defaults 0 1\n')
    (root/'home/blikvm/.ssh/authorized_keys').write_bytes(b'')
    (root/'etc/systemd/system/serial-getty@ttyS0.service.d/lab.conf').unlink()
    standalone_network(root, revision)
    # Normalize all mtimes, including symlinks, root and modified directories.
    for current, dirs, files in os.walk(root, topdown=False):
        for n in dirs + files:
            os.utime(Path(current)/n, (EPOCH, EPOCH), follow_symlinks=False)
        os.utime(current, (EPOCH, EPOCH))
    expected = inventory(root)
    delta = [n for n in sorted(set(original)|set(expected)) if original.get(n) != expected.get(n)]
    allowed = {'boot/Image','boot/sun50i-h616-blikvm-v4.dtb','boot/boot.cmd','boot/boot.scr','etc/fstab','home/blikvm/.ssh/authorized_keys','etc/systemd/system/serial-getty@ttyS0.service.d/lab.conf'}
    if revision == 'p2-r1-candidate1':
        allowed.add(NETWORK_PATH)
    # Only timestamp normalization may change other existing entries.
    for n in set(delta)-allowed:
        old, new = dict(original[n]), dict(expected[n]); old.pop('mtime'); new.pop('mtime'); assert old == new, n
    expected['lost+found'] = {'mode':0o700,'uid':0,'gid':0,'mtime':EPOCH,'type':stat.S_IFDIR}
    save(dest/'filesystem-manifest.json', expected)
    save(dest/'rootfs-delta.json', {'payload_or_access_changes':sorted(allowed),'all_changes':delta,'mtime_policy':EPOCH})
    fs = work/'root.ext4'
    with fs.open('xb') as f:
        f.truncate(ROOT_SIZE)
    args = ['mkfs.ext4', '-F', '-q', '-b', '4096', '-I', '256', '-N', '65536', '-m', '0',
            '-U', UUID, '-L', LABEL, '-E', f'lazy_itable_init=0,lazy_journal_init=0,nodiscard,hash_seed={UUID}',
            '-d', root, fs]
    p = run(args); (work/'mkfs.log').write_bytes(p.stdout+p.stderr)
    normalize(fs, root, work)
    image = dest/'blikvm-v4-pikvm.img'
    with image.open('xb') as f:
        f.write(bytes(OFFSET))
        with fs.open('rb') as source:
            shutil.copyfileobj(source, f, 1024**2)
        f.seek(0); f.write(mbr())
        for x in vendor['bootloader_extents']:
            f.seek(x['offset']); f.write((vendor_dir/x['name']).read_bytes())
        f.flush(); os.fsync(f.fileno())
    assert image.stat().st_size == SIZE and image.stat().st_blocks*512 >= SIZE
    validation = validate(image, work, expected, lock, vendor)
    save(dest/'validation.json', validation)
    compressed = dest/'blikvm-v4-pikvm.img.zst'
    run(['zstd', '-q', '-19', '-T1', '--no-progress', image, '-o', compressed])
    # Test compressed frame and fully verify decompression, not just frame checksum.
    compressed.chmod(0o644)
    run(['zstd', '-t', compressed])
    p = subprocess.Popen(['zstd', '-q', '-d', '-c', str(compressed)], stdout=subprocess.PIPE)
    decoded = hashlib.file_digest(p.stdout, 'sha256').hexdigest(); assert p.wait() == 0 and decoded == digest(image)
    partition = {'table':'dos','disk_id':'b14b0001','sector_size':512,'image_size':SIZE,
                 'partitions':[{'number':1,'start_sector':8192,'sectors':2097152,'end_sector_inclusive':2105343,
                                'type':'83','bootable':True,'filesystem':'ext4','uuid':UUID,'partuuid':PARTUUID,'label':LABEL}]}
    save(dest/'partition-layout.json', partition); save(dest/'bootloader-layout.json', vendor)
    versions = {}
    for name, args in {'mke2fs':['mkfs.ext4','-V'],'debugfs':['debugfs','-V'],'zstd':['zstd','--version'],
                       'mkimage':['mkimage','-V'],'sfdisk':['sfdisk','--version'],'python':['python3','--version']}.items():
        p = run(args); versions[name] = (p.stdout+p.stderr).decode().strip()
    manifest = {'schema_version':1, **lock, 'standalone_revision':revision, 'linux_version':'7.2.3-blikvm-v4-m8f0-ms2131c2',
                'ubuntu':{'version':'26.04.1','snapshot':'20260906T000000Z','base_sha256':'5a1906794ced63a71a8119c3f211ef5f0bbe0a243001b4bbd41fdf80c5b219fd'},
                'partition_layout':partition,'vendor_bootloader':vendor,'tool_versions':versions,
                'tool_binary_sha256':{name:digest(Path(shutil.which(name))) for name in ['mke2fs','debugfs','e2fsck','mkimage','zstd','sfdisk']},
                'assembler_sha256':digest(Path(__file__)),
                'assembly_source_sha256':{p.name:digest(p) for p in sorted(HERE.iterdir()) if p.is_file()}, 'mke2fs_config_sha256':digest(HERE/'mke2fs.conf'),
                'builder':{'type':'native Build VM','os_release':Path('/etc/os-release').read_text(),'architecture':os.uname().machine},
                'boot_cmd_sha256':digest(root/'boot/boot.cmd'),'boot_scr_sha256':digest(root/'boot/boot.scr'),
                'rootfs_inventory_sha256':digest(dest/'filesystem-manifest.json'),
                'image_sha256':digest(image),'compressed_image_sha256':digest(compressed),
                'compression_options':['-19','-T1'],'image_size':SIZE,'compressed_size':compressed.stat().st_size,
                'physical_sd_written':False,'standalone_hardware_boot':'NOT_TESTED','atx':'DEFERRED'}
    save(dest/'manifest.json', manifest)
    (dest/'SHA256SUMS').write_text(''.join(f'{digest(dest/n)}  {n}\n' for n in ['blikvm-v4-pikvm.img','blikvm-v4-pikvm.img.zst','manifest.json','partition-layout.json','bootloader-layout.json','filesystem-manifest.json']))
    print(json.dumps({'output':str(dest),'image_sha256':manifest['image_sha256'],'compressed_image_sha256':manifest['compressed_image_sha256']}))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--vendor-dir', type=Path, default=REPO/'out/p1/vendor')
    p.add_argument('--revision', choices=['p1', 'p2-r1-candidate1'], default='p1')
    a = p.parse_args()
    assemble(a.output, a.vendor_dir.resolve(), a.revision)
