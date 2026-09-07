#!/usr/bin/env python3
"""Enroll a dedicated lab CA and SAN certificate into a private RAM overlay.

Reuse the M8-B credential/SSH enrollment without modifying it. All private
outputs belong in an ignored directory and must never enter public evidence.
"""
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import runpy
import shutil
import subprocess
import tarfile


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--private-dir', type=Path, required=True)
    p.add_argument('--previous-private', type=Path, required=True)
    p.add_argument('--artifacts', type=Path, required=True)
    a = p.parse_args()
    os.umask(0o077)
    d = a.private_dir.resolve()
    d.mkdir(mode=0o700, parents=True, exist_ok=False)
    for name in ('credentials.json', 'htpasswd', 'id_ed25519', 'id_ed25519.pub', 'bridge_key'):
        shutil.copyfile(a.previous_private / name, d / name)
    def openssl(*args):
        subprocess.run(['openssl', *args], check=True, stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL)
    openssl('req', '-x509', '-newkey', 'rsa:3072', '-sha256', '-nodes', '-days', '365',
            '-subj', '/CN=BliKVM M8-C Development CA',
            '-addext', 'basicConstraints=critical,CA:TRUE,pathlen:0',
            '-addext', 'keyUsage=critical,keyCertSign,cRLSign',
            '-keyout', str(d/'ca.key'), '-out', str(d/'ca.crt'))
    openssl('req', '-new', '-newkey', 'rsa:3072', '-nodes',
            '-subj', '/CN=blikvm-v4.lab', '-keyout', str(d/'server.key'),
            '-out', str(d/'server.csr'))
    extensions = ('basicConstraints=critical,CA:FALSE\n'
                  'keyUsage=critical,digitalSignature,keyEncipherment\n'
                  'extendedKeyUsage=serverAuth\n'
                  'subjectAltName=DNS:blikvm-v4.lab,IP:192.168.88.2\n'
                  'subjectKeyIdentifier=hash\nauthorityKeyIdentifier=keyid,issuer\n')
    (d/'server.ext').write_text(extensions)
    openssl('x509', '-req', '-in', str(d/'server.csr'), '-CA', str(d/'ca.crt'),
            '-CAkey', str(d/'ca.key'), '-CAcreateserial', '-days', '30', '-sha256',
            '-extfile', str(d/'server.ext'), '-out', str(d/'server.crt'))
    openssl('verify', '-CAfile', str(d/'ca.crt'), '-verify_hostname', 'blikvm-v4.lab', str(d/'server.crt'))
    with tarfile.open(a.artifacts/'rootfs.tar.gz') as tar:
        authorized = tar.extractfile('./home/blikvm/.ssh/authorized_keys').read()
        passwd = tar.extractfile('./etc/passwd').read().decode()
    uid = int(next(s.split(':')[2] for s in passwd.splitlines() if s.startswith('kvmd:')))
    entries = [(name, b'', 0o40755, 0, 0) for name in
               ('etc', 'etc/kvmd', 'etc/kvmd/nginx', 'etc/kvmd/nginx/ssl')]
    entries += [('etc/kvmd/htpasswd', (d/'htpasswd').read_bytes(), 0o100400, uid, 0),
                ('etc/kvmd/nginx/ssl/server.crt', (d/'server.crt').read_bytes(), 0o100644, 0, 0),
                ('etc/kvmd/nginx/ssl/server.key', (d/'server.key').read_bytes(), 0o100600, 0, 0),
                ('home/blikvm/.ssh/authorized_keys', authorized.rstrip()+b'\n'+
                 (d/'id_ed25519.pub').read_bytes(), 0o100600, 1000, 1000)]
    newc = runpy.run_path(str(Path(__file__).parents[1]/'kvmd-web/provision.py'))['newc']
    overlay = gzip.compress(newc(entries), mtime=0)
    (d/'enrollment.cpio.gz').write_bytes(overlay)
    image = (a.artifacts/'initramfs.cpio.gz').read_bytes()+overlay
    assert len(image) < 0x6000000, 'frozen 96 MiB limit'
    (d/'initramfs.cpio.gz').write_bytes(image)
    print(json.dumps({'size':len(image), 'sha256':hashlib.sha256(image).hexdigest()}))


if __name__ == '__main__':
    main()
