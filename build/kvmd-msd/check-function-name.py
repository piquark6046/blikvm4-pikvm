#!/usr/bin/env python3
"""Replay E0 patch against the hash-locked upstream archive in a temp tree."""
import ast
import hashlib
from pathlib import Path
import subprocess
import tarfile
import tempfile
from types import SimpleNamespace

repo = Path(__file__).resolve().parents[2]
archive = repo / 'out/kvmd-web/downloads/kvmd.tar.gz'
assert hashlib.sha256(archive.read_bytes()).hexdigest() == '669a21aafd7e08ca85d02a965a8f3f76b3ba63ac8539ece385b1f676bdf7fdf7'
with tempfile.TemporaryDirectory() as temporary:
    root = Path(temporary)
    with tarfile.open(archive) as tar:
        for name in ('drive.py', '__init__.py'):
            suffix = 'kvmd/plugins/msd/otg/' + name
            member = next(m for m in tar.getmembers() if m.name.endswith('/' + suffix))
            path = root / suffix
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(tar.extractfile(member).read())
    subprocess.run(['patch', '--batch', '--fuzz=0', '-p1', '-i', str(repo / 'build/kvmd-msd/function-name.patch')], cwd=root, check=True)
    source = ast.parse((root / 'kvmd/plugins/msd/otg/drive.py').read_text())
    # Drive only depends on usb path construction and its exception base.
    source.body = [n for n in source.body if not isinstance(n, ast.ImportFrom)]
    gadget = root / 'configfs/blikvm_m5'
    ns = {'usb': SimpleNamespace(G_PROFILE='configs/c.1', G_FUNCTIONS='functions',
                                get_gadget_path=lambda *p: str(gadget.joinpath(*p))),
          'MsdOperationError': RuntimeError}
    exec(compile(source, 'drive.py', 'exec'), ns)
    Drive = ns['Drive']
    assert Drive(2, 3).get_name() == 'mass_storage.usb2/lun.3'
    drive = Drive(0, 0, 'mass_storage.g4')
    assert not drive.is_enabled()
    lun = gadget / 'functions/mass_storage.g4/lun.0'
    lun.mkdir(parents=True)
    config = gadget / 'configs/c.1'
    config.mkdir(parents=True)
    (config / 'mass_storage.g4').symlink_to(lun.parent)
    (lun / 'file').write_text('/approved/g4.img\n')
    (lun / 'ro').write_text('1\n')
    (lun / 'cdrom').write_text('0\n')
    assert drive.is_enabled()
    assert drive.get_name() == 'mass_storage.g4/lun.0'
    assert drive.get_watchable_paths() == [str(lun), str(config)]
    assert drive.get_image_path() == '/approved/g4.img'
    assert not drive.get_rw_flag() and not drive.get_cdrom_flag()
    for name in ('/tmp/path', '../mass_storage.g4', 'mass_storage.g4/lun.0',
                 'hid.keyboard', 'mass_storage.', 'mass_storage.g4\n', 'mass_storage...'):
        try:
            Drive(0, 0, name)
        except ValueError:
            pass
        else:
            raise AssertionError('accepted invalid function ' + repr(name))
    try:
        Drive(0, -1)
    except ValueError:
        pass
    else:
        raise AssertionError('accepted negative LUN')
    plugin = (root / 'kvmd/plugins/msd/otg/__init__.py').read_text()
    ast.parse(plugin)
    assert 'Drive(instance=0, lun=0, function=c.function)' in plugin
print('PASS: upstream default, G4 path/readback, malformed names, negative LUN, plugin wiring')
