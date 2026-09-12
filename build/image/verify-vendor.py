#!/usr/bin/env python3
"""Replay vendor prefix provenance, partition table, SPL checksum and FIT extents."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import subprocess


def verify(prefix, expected):
    b = prefix.read_bytes()
    sha = lambda data: hashlib.sha256(data).hexdigest()
    assert len(b) == expected['source_prefix_size']
    assert sha(b) == expected['source_prefix_sha256']
    assert b[510:512] == b'\x55\xaa'
    assert f'{struct.unpack_from("<I", b, 440)[0]:08x}' == expected['table_id']
    for p in expected['partitions']:
        entry = b[446+(p['number']-1)*16:462+(p['number']-1)*16]
        assert entry[4] == int(p['type'],16)
        assert struct.unpack_from('<II',entry,8) == (p['start_sector'],p['sectors'])
    assert b[494:510] == bytes(16)
    parts = sorted(expected['partitions'], key=lambda p:p['start_sector'])
    end = 2048
    for p in parts:
        assert p['start_sector'] == end
        end += p['sectors']
    assert end*512 == expected['source_size']
    for start, end in expected['other_raw_bytes_zero']:
        assert not any(b[start:end])
    spl_info, fit_info = expected['bootloader_extents']
    for x in expected['bootloader_extents']:
        assert sha(b[x['offset']:x['offset']+x['size']]) == x['sha256']
    off = spl_info['offset']; spl = bytearray(b[off:off+spl_info['size']])
    assert spl[4:12] == b'eGON.BT0'
    checksum, length = struct.unpack_from('<II',spl,12)
    assert length == len(spl)
    struct.pack_into('<I',spl,12,0x5f0a6c39)
    assert sum(struct.unpack(f'<{length//4}I',spl)) & 0xffffffff == checksum
    base = fit_info['offset']; fit = b[base:base+fit_info['size']]
    magic,n,st,ss,_,_,_,_,slen,stlen = struct.unpack_from('>10I',fit)
    assert magic == 0xd00dfeed and n == len(fit)
    pos = st; stack = []; components = []; props = {}
    while pos < st+stlen:
        token = struct.unpack_from('>I',fit,pos)[0]; pos += 4
        if token == 1:
            end = fit.index(0,pos); stack.append(fit[pos:end].decode()); pos=(end+4)&~3
        elif token == 2:
            stack.pop()
        elif token == 3:
            size,no = struct.unpack_from('>II',fit,pos); pos += 8
            end=fit.index(0,ss+no); name=fit[ss+no:end].decode()
            if name == 'data':
                components.append({'name':stack[-1],'offset':base+pos,'size':size,'sha256':sha(fit[pos:pos+size])})
            else:
                props['/'.join(stack)+'/'+name] = fit[pos:pos+size].hex()
            pos = (pos+size+3)&~3
        elif token == 9:
            break
        else:
            assert token == 4
    assert components == expected['fit_components']
    assert props == expected['fit_properties_hex']
    return {'result':'passed','prefix_sha256':sha(b),'spl_checksum_valid':True,
            'fit_components_verified':len(components),'all_unpartitioned_bytes_classified':True}


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('prefix',type=Path)
    p.add_argument('--layout',type=Path,default=Path(__file__).resolve().parents[2]/'research/evidence/p1/vendor-layout.json')
    a=p.parse_args()
    print(json.dumps(verify(a.prefix,json.loads(a.layout.read_text())),indent=2))
