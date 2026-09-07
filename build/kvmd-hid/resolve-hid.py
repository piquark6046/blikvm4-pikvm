#!/usr/bin/python3
"""Validate frozen functions before granting access to exactly their devices."""
import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import stat

GADGET = Path('/sys/kernel/config/usb_gadget/blikvm_m5')
ROLES = {'keyboard': (8, 1, 1), 'absolute': (5, 0, 0), 'relative': (3, 0, 0)}


def resolve(gadget=GADGET, sysroot=Path('/sys'), devroot=Path('/dev'),
            descriptors=Path('/usr/lib/kvmd-hid/descriptors')):
    udc = (gadget / 'UDC').read_text().strip()
    udc_path = (sysroot / 'class/udc' / udc).resolve(strict=True)
    if not udc or '5100000.usb' not in udc_path.parts:
        raise RuntimeError('expected bound H616 USB0 controller')
    if {p.name for p in (gadget / 'functions').iterdir()} != {
            'hid.keyboard', 'hid.absolute', 'hid.relative', 'mass_storage.g4'}:
        raise RuntimeError('unexpected gadget function layout')
    result = []
    for role, (length, subclass, protocol) in ROLES.items():
        function = gadget / 'functions' / ('hid.' + role)
        for name, expected in {'report_length': length, 'subclass': subclass,
                               'protocol': protocol, 'no_out_endpoint': 1}.items():
            if int((function / name).read_text()) != expected:
                raise RuntimeError('frozen function attribute mismatch: ' + role + '/' + name)
        report = (function / 'report_desc').read_bytes()
        if report != (descriptors / role).read_bytes():
            raise RuntimeError('frozen report descriptor mismatch: ' + role)
        number = (function / 'dev').read_text().strip()
        if not re.fullmatch(r'\d+:\d+', number):
            raise RuntimeError('invalid function device number')
        identity = (sysroot / 'dev/char' / number).resolve(strict=True)
        if not re.fullmatch(r'hidg\d+', identity.name):
            raise RuntimeError('unexpected sysfs HID identity')
        if (identity / 'dev').read_text().strip() != number:
            raise RuntimeError('sysfs device number mismatch')
        node = devroot / identity.name
        info = node.lstat()
        if not stat.S_ISCHR(info.st_mode) or (os.major(info.st_rdev), os.minor(info.st_rdev)) != tuple(map(int, number.split(':'))):
            raise RuntimeError('character device identity mismatch')
        link = gadget / 'configs/c.1' / ('hid.' + role)
        if link.resolve(strict=True) != function.resolve(strict=True):
            raise RuntimeError('function configuration link mismatch')
        result.append(dict(role=role, function=str(function), dev=number,
                           sysfs=str(identity), node=str(node),
                           stable=str(devroot / ('kvmd-hid-' + role)),
                           descriptor_sha256=hashlib.sha256(report).hexdigest()))
    if len({row['dev'] for row in result}) != 3:
        raise RuntimeError('duplicate function device number')
    return result


def main():
    rows = resolve()  # Validate all three before any permission mutation.
    uid = pwd.getpwnam('kvmd').pw_uid
    for row in rows:
        os.chown(row['node'], uid, 0)
        os.chmod(row['node'], 0o600)
        link = Path(row['stable'])
        if link.is_symlink():
            link.unlink()
        elif link.exists():
            raise RuntimeError('refusing to replace non-symlink stable identity')
        link.symlink_to(row['node'])
    destination = Path('/run/kvmd-hid')
    destination.mkdir(mode=0o755, exist_ok=True)
    (destination / 'mapping.json').write_text(json.dumps(rows, indent=2) + '\n')
    print(json.dumps(rows))


if __name__ == '__main__':
    main()
