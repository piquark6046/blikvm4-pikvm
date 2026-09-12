#!/usr/bin/env python3
"""Prove public raw images exclude every supplied private enrollment payload."""
import argparse
import hashlib
import json
import mmap
from pathlib import Path
import re


def verify(images, enrollment):
    provenance=json.loads((enrollment/'provenance.json').read_text())
    needles=[]
    for name,meta in provenance['files'].items():
        p=enrollment/name
        assert p.is_file() and not p.is_symlink()
        data=p.read_bytes();assert hashlib.sha256(data).hexdigest()==meta['sha256']
        # Include individual authorized-key lines and individual PEM payload lines,
        # so fragmentation or concatenation cannot hide the enrolled material.
        needles.append(data)
        needles.extend(line for line in data.splitlines() if len(line)>=32 and not line.startswith(b'-----'))
    result=[]
    for image in images:
        with image.open('rb') as f, mmap.mmap(f.fileno(),0,access=mmap.ACCESS_READ) as raw:
            assert not any(raw.find(needle) >= 0 for needle in needles), 'private enrollment bytes in public image'
            # Also recognize the accepted auth encoding anywhere, independently
            # of the exact enrolled hash or its filesystem location.
            assert not re.search(rb'\{SSHA512\}[A-Za-z0-9+/]{107}=',raw), 'SSHA512 material in public image'
        with image.open('rb') as f:h=hashlib.file_digest(f,'sha256').hexdigest()
        result.append({'image_sha256':h,'bytes_scanned':image.stat().st_size,'enrollment_payloads_absent':True,'SSHA512_records_absent':True})
    return {'result':'passed','images':result,'enrollment_files_checked':len(provenance['files']),
            'private_values_or_hashes_published':False}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--enrollment',type=Path,required=True)
    p.add_argument('images',type=Path,nargs='+')
    a=p.parse_args();print(json.dumps(verify(a.images,a.enrollment),indent=2))
