#!/usr/bin/env python3
"""Generate private lab enrollment separately from the reproducible public image.

The output directory must remain outside Git. Reuse it across qualification
boots; never publish or archive its secret contents with the public evidence.
"""
import argparse
import base64
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import secrets
import subprocess
import tarfile


def newc(entries):
    out = io.BytesIO()
    for index, (name, data, mode, uid, gid) in enumerate(
            [*entries, ('TRAILER!!!', b'', 0, 0, 0)]):
        name = name.encode() + b'\0'
        fields = (index, mode, uid, gid, 1, 1788652800, len(data),
                  0, 0, 0, 0, len(name), 0)
        out.write(b'070701' + ''.join(f'{x:08x}' for x in fields).encode())
        out.write(name)
        out.write(b'\0' * (-out.tell() % 4))
        out.write(data)
        out.write(b'\0' * (-out.tell() % 4))
    out.write(b'\0' * (-out.tell() % 512))
    return out.getvalue()


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--private-dir', type=Path, required=True)
    p.add_argument('--artifacts', type=Path, required=True)
    a = p.parse_args()
    os.umask(0o077)
    d = a.private_dir.resolve()
    d.mkdir(mode=0o700, parents=True, exist_ok=False)
    password = secrets.token_urlsafe(32)
    (d/'credentials.json').write_text(json.dumps({'user': 'qualifier', 'passwd': password}))
    salt = secrets.token_bytes(16)
    htpasswd = b'qualifier:{SSHA512}' + base64.b64encode(
        hashlib.sha512(password.encode() + salt).digest() + salt) + b'\n'
    (d/'htpasswd').write_bytes(htpasswd)
    subprocess.run(['openssl', 'req', '-x509', '-newkey', 'rsa:3072', '-sha256',
                    '-nodes', '-days', '30', '-subj', '/CN=blikvm.local',
                    '-addext', 'subjectAltName=DNS:blikvm.local,DNS:localhost,IP:127.0.0.1',
                    '-keyout', str(d/'server.key'), '-out', str(d/'server.crt')],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run(['ssh-keygen', '-q', '-t', 'ed25519', '-N', '',
                    '-C', 'm8b-build-vm', '-f', str(d/'id_ed25519')], check=True)
    with tarfile.open(a.artifacts/'rootfs.tar.gz') as tar:
        authorized = tar.extractfile('./home/blikvm/.ssh/authorized_keys').read()
        passwd = tar.extractfile('./etc/passwd').read().decode()
    uid = int(next(x.split(':')[2] for x in passwd.splitlines() if x.startswith('kvmd:')))
    entries = [(name, b'', 0o40755, 0, 0) for name in
               ('etc', 'etc/kvmd', 'etc/kvmd/nginx', 'etc/kvmd/nginx/ssl')]
    entries += [
        ('etc/kvmd/htpasswd', htpasswd, 0o100400, uid, 0),
        ('etc/kvmd/nginx/ssl/server.crt', (d/'server.crt').read_bytes(), 0o100644, 0, 0),
        ('etc/kvmd/nginx/ssl/server.key', (d/'server.key').read_bytes(), 0o100600, 0, 0),
        ('home/blikvm/.ssh/authorized_keys', authorized.rstrip()+b'\n'+
         (d/'id_ed25519.pub').read_bytes(), 0o100600, 1000, 1000),
    ]
    overlay = gzip.compress(newc(entries), mtime=0)
    (d/'enrollment.cpio.gz').write_bytes(overlay)
    image = (a.artifacts/'initramfs.cpio.gz').read_bytes() + overlay
    if len(image) >= 0x6000000:
        raise RuntimeError('Private qualification image exceeds frozen 96 MiB RAM bound')
    (d/'initramfs.cpio.gz').write_bytes(image)
    print(json.dumps({'private_image_sha256': hashlib.sha256(image).hexdigest(),
                      'size': len(image), 'secrets_in_git': False}))


if __name__ == '__main__':
    main()
