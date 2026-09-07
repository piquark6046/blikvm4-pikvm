#!/usr/bin/python3
"""Bounded M8-E media delegate; never creates or binds a gadget."""
import hashlib
import json
import os
from pathlib import Path
import pwd
import socket
import stat
import struct

GADGET = Path('/sys/kernel/config/usb_gadget/blikvm_m5')
FUNCTION = 'mass_storage.g4'
LUN = 'lun.0'
ROOT = Path('/usr/share/kvmd-msd/images')
CATALOG = Path('/usr/share/kvmd-msd/catalog.json')
SOCKET = '/run/kvmd-msd/control.sock'
LEGACY = Path('/usr/share/g4-storage.img')
G4_HASH = '14845cb5d5d773bc3b7411d2e939b948abc9a7fcc04229159f32a355777ec45b'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def secure_path(path, directory=False):
    require(path.is_absolute() and path.resolve(strict=True) == path, 'noncanonical path')
    for parent in (path, *path.parents):
        st = parent.lstat()
        require(st.st_uid == 0 and not st.st_mode & 0o022, 'untrusted ownership/mode')
        require(not stat.S_ISLNK(st.st_mode), 'symlink')
    require(stat.S_ISDIR(path.stat().st_mode) if directory else stat.S_ISREG(path.stat().st_mode), 'wrong file type')


def catalog():
    secure_path(CATALOG)
    secure_path(ROOT, True)
    data = json.loads(CATALOG.read_text())
    require(set(data) == {'g4-storage.img'}, 'unexpected catalog')
    require(data['g4-storage.img'] == {'size': 8388608, 'sha256': G4_HASH}, 'catalog drift')
    require({p.name for p in ROOT.iterdir()} == set(data), 'unapproved catalog files')
    for name, expected in data.items():
        p = ROOT / name
        secure_path(p)
        require(p.stat().st_nlink == 1, 'linked image')
        require(p.stat().st_size == expected['size'], 'image size drift')
        require(hashlib.sha256(p.read_bytes()).hexdigest() == expected['sha256'], 'image hash drift')
    return data


def validate():
    require(GADGET.resolve(strict=True) == GADGET, 'gadget path mismatch')
    require({p.name for p in GADGET.parent.iterdir()} == {'blikvm_m5'}, 'gadget count/identity mismatch')
    require((GADGET/'idVendor').read_text().strip() == '0x1d6b', 'VID mismatch')
    require((GADGET/'idProduct').read_text().strip() == '0x0106', 'PID mismatch')
    for name, expected in {'manufacturer':'BliKVM', 'product':'BliKVM M5 keyboard',
                           'serialnumber':'blikvm-v4-m5-keyboard'}.items():
        require((GADGET/'strings/0x409'/name).read_text().strip() == expected, 'USB string identity mismatch')
    funcs = {'hid.keyboard', 'hid.absolute', 'hid.relative', FUNCTION}
    require({p.name for p in (GADGET/'functions').iterdir()} == funcs, 'function layout mismatch')
    udc = (GADGET/'UDC').read_text().strip()
    require(bool(udc) and '/' not in udc, 'UDC missing')
    require('5100000.usb' in (Path('/sys/class/udc')/udc).resolve(strict=True).parts, 'wrong UDC')
    config = GADGET/'configs/c.1'
    require({p.name for p in config.iterdir() if p.is_symlink()} == funcs, 'profile mismatch')
    for name in funcs:
        require((config/name).resolve(strict=True) == GADGET/'functions'/name, 'function link mismatch')
    function = GADGET/'functions'/FUNCTION
    require(function.resolve(strict=True) == function, 'function identity mismatch')
    require({p.name for p in function.glob('lun.*')} == {LUN}, 'LUN layout mismatch')
    lun = function/LUN
    require(lun.resolve(strict=True) == lun, 'LUN path mismatch')
    require((function/'stall').read_text().strip() == '1', 'stall drift')
    for name, expected in {'ro':'1', 'cdrom':'0', 'removable':'0', 'nofua':'0',
                           'inquiry_string':'BliKVM  G4 RAM RO       0001'}.items():
        require((lun/name).read_text().strip() == expected, 'LUN attribute drift: '+name)
    return lun


def adopt():
    """One exact frozen boot path can be adopted before accepting requests."""
    lun = validate()
    catalog()
    current = (lun/'file').read_text().strip()
    if current == str(LEGACY):
        secure_path(LEGACY)
        require(hashlib.sha256(LEGACY.read_bytes()).hexdigest() == G4_HASH, 'legacy image drift')
        (lun/'file').write_text(str(ROOT/'g4-storage.img')+'\n')
    else:
        require(current in ('', str(ROOT/'g4-storage.img')), 'unapproved active medium')
    validate()


def operate(request):
    require(type(request) is dict, 'invalid request')
    op = request.get('operation')
    require(op in ('attach', 'eject'), 'unsupported operation')
    keys = {'operation','gadget','function','lun'} | ({'image'} if op == 'attach' else set())
    require(set(request) == keys, 'unexpected fields')
    require((request['gadget'], request['function'], request['lun']) == ('blikvm_m5', FUNCTION, LUN), 'identity mismatch')
    lun = validate()
    approved = catalog()
    current = (lun/'file').read_text().strip()
    require(current == '' or current in {str(ROOT/n) for n in approved}, 'unapproved active medium')
    if op == 'attach':
        require(type(request['image']) is str and request['image'] in approved, 'unapproved image')
        require(not current, 'medium already attached')
        expected = str(ROOT/request['image'])
        (lun/'file').write_text(expected+'\n')
    else:
        require(bool(current), 'medium already ejected')
        expected = ''
        (lun/'forced_eject').write_text('\n')
    validate()
    require((lun/'file').read_text().strip() == expected, 'attachment readback mismatch')
    catalog()
    return {'ok': True}


def main():
    adopt()
    uid = pwd.getpwnam('kvmd').pw_uid
    if os.path.lexists(SOCKET):
        require(stat.S_ISSOCK(os.lstat(SOCKET).st_mode), 'unexpected socket path')
        os.unlink(SOCKET)
    with socket.socket(socket.AF_UNIX) as server:
        server.bind(SOCKET)
        os.chmod(SOCKET, 0o600)
        os.chown(SOCKET, uid, -1)
        server.listen(4)
        while True:
            conn, _ = server.accept()
            with conn:
                conn.settimeout(2)
                try:
                    peer = struct.unpack('3i', conn.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
                    require(peer[1] == uid, 'unauthorized peer')
                    data = b''
                    while not data.endswith(b'\n') and len(data) <= 1024:
                        chunk = conn.recv(1025-len(data))
                        require(bool(chunk), 'incomplete request')
                        data += chunk
                    require(len(data) <= 1024, 'request too large')
                    result = operate(json.loads(data))
                except Exception as ex:
                    result = {'ok': False, 'error': str(ex)}
                    print(json.dumps(result), flush=True)
                try:
                    conn.sendall(json.dumps(result).encode()+b'\n')
                except OSError:
                    pass


if __name__ == '__main__':
    main()
