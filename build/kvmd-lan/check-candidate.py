#!/usr/bin/env python3
"""Compare the built derivative with the frozen M8-B public rootfs."""
import hashlib
import json
from pathlib import Path
import tarfile


def inventory(path):
    result = {}
    with tarfile.open(path, 'r|gz') as archive:
        for item in archive:
            if item.isfile():
                result[item.name] = hashlib.file_digest(archive.extractfile(item), 'sha256').hexdigest()
    return result


before = inventory('out/kvmd-web/artifacts/rootfs.tar.gz')
after = inventory('out/kvmd-lan/artifacts/rootfs.tar.gz')
frozen = [n for n in before if any(v in n for v in
          ('/kvmd/', '/hid-', '/gadget-', '/ustreamer', '/usr/bin/kvmd', '/kvmd.service', '/99-blikvm-video.rules'))]
changes = sorted(n for n in frozen if before[n] != after.get(n))
assert changes == ['./etc/kvmd/nginx/nginx.conf'], changes
for secret in ('./etc/kvmd/htpasswd', './etc/kvmd/nginx/ssl/server.key'):
    assert secret not in after, secret
b = dict(line.split('\t',1) for line in Path('build/kvmd-web/packages.lock.tsv').read_text().splitlines())
a = dict(line.split('\t',1) for line in Path('build/kvmd-lan/packages.lock.tsv').read_text().splitlines())
assert all(a.get(k) == v for k,v in b.items()), 'frozen package versions changed'
assert set(a)-set(b) == {'libjansson4','libnftables1','libnftnl11','nftables'}, set(a)-set(b)
print(json.dumps({'result':'passed','frozen_files_compared':len(frozen),
                  'allowed_changed_files':changes,'additional_packages':sorted(set(a)-set(b)),
                  'public_image_has_no_enrollment':True},indent=2))
