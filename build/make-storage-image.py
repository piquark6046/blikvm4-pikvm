#!/usr/bin/env python3
"""Generate the fixed G4 8 MiB FAT16 superfloppy without host mounts/tools."""
import hashlib
import json
from pathlib import Path
import struct
import sys

FILES = {'README.TXT': b'BliKVM G4 disposable read-only qualification medium.\r\n',
         'PATTERN.BIN': bytes(range(256)) * 4}
SIZE = 8 * 1024 * 1024

def build_image():
    image = bytearray(SIZE)
    image[:11] = b'\xeb\x3c\x90BLIKVMG4'
    struct.pack_into('<HBHBHHBHHHII', image, 11,
                     512, 2, 1, 2, 512, 16384, 0xf8, 32, 32, 64, 0, 0)
    struct.pack_into('<BBBI', image, 36, 0x80, 0, 0x29, 0x47340001)
    image[43:62] = b'BLIKVM_G4  FAT16   '
    image[510:512] = b'\x55\xaa'
    fat = bytearray(32 * 512)
    struct.pack_into('<HH', fat, 0, 0xfff8, 0xffff)
    root = 65 * 512
    image[root:root+11] = b'BLIKVM_G4  '
    image[root+11] = 8
    for index, (name, data) in enumerate(FILES.items(), 1):
        cluster = index + 1
        struct.pack_into('<H', fat, cluster * 2, 0xffff)
        entry = root + index * 32
        stem, ext = name.split('.')
        image[entry:entry+11] = (stem.ljust(8) + ext.ljust(3)).encode()
        image[entry+11] = 0x20
        # Fixed 1980-01-01 FAT dates, midnight; no host timestamps.
        for offset in (16, 18, 24):
            struct.pack_into('<H', image, entry+offset, 33)
        struct.pack_into('<HI', image, entry+26, cluster, len(data))
        start = (97 + (cluster-2)*2) * 512
        image[start:start+len(data)] = data
    image[512:33*512] = fat
    image[33*512:65*512] = fat
    return bytes(image)

def manifest():
    return {'size': SIZE, 'logical_block_size': 512, 'sectors': SIZE//512,
            'filesystem': 'vfat', 'fat_type': 'FAT16', 'label': 'BLIKVM_G4',
            'uuid': '4734-0001', 'partition_table': None,
            'sha256': hashlib.sha256(build_image()).hexdigest(),
            'files': {n: {'size': len(d), 'sha256': hashlib.sha256(d).hexdigest()}
                      for n, d in FILES.items()}}

if __name__ == '__main__':
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    (out/'g4-storage.img').write_bytes(build_image())
    (out/'g4-storage.json').write_text(json.dumps(manifest(), indent=2)+'\n')
    (out/'g4-storage.sha256').write_text(manifest()['sha256']+'  /usr/share/g4-storage.img\n')
