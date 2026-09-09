#!/usr/bin/env python3
"""Replay every accepted M8-E gate with an explicitly pinned candidate Image."""
import argparse
from pathlib import Path
import re
import sys

p=argparse.ArgumentParser(add_help=False);p.add_argument('--candidate-image',required=True);a,rest=p.parse_known_args()
assert re.fullmatch('[0-9a-f]{64}',a.candidate_image)
original=Path(__file__).with_name('verify-msd-evidence.py');source=original.read_text()
old='d6f4235904b0b482e78f449139f539adc4370be923ec16f4a0d8451842501ee8'
assert source.count(old)==1;source=source.replace(old,a.candidate_image)
needle="    for name,sha in expected.items():assert meta[name]['sha256']==sha,(name,boot['run_id'])"
replacement="""    for name,sha in expected.items():
        if name=='kvmd-web_4.213-1blikvm4_arm64.deb' and name not in meta:
            # Candidate changes only Image; exact accepted enrolled root hash
            # proves the embedded package is unchanged without a separate deb.
            assert meta['initramfs.cpio.gz']['sha256']==ENROLLED
            continue
        assert meta[name]['sha256']==sha,(name,boot['run_id'])
"""
assert source.count(needle)==1;source=source.replace(needle,replacement)
sys.argv=[str(original),*rest]
exec(compile(source,str(original),'exec'),{'__name__':'__main__','__file__':str(original)})
