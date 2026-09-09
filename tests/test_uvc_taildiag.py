import json
from pathlib import Path
import runpy
import struct
import unittest

ROOT=Path(__file__).resolve().parents[1]
MODULE=runpy.run_path(str(ROOT/'lab/uvc-taildiag-read.py'))
SCHEMA=json.loads((ROOT/'build/linux-diagnostics/uvc-taildiag-schema.json').read_text())

class UVCTailDiagnosticTests(unittest.TestCase):
    def fixture(self,missing=False,corrupt=False):
        payload=b'\xff\xd8\xff\xd9'+b'\x0c\x8e'+bytes(range(10))
        raw=b'\x02\x82'+payload
        s=SCHEMA;size=MODULE['layout'](s);data=bytearray(size['frame']+len(payload))
        def put(names,row,offset):struct.pack_into('<'+'q'*len(names),data,offset,*(row.get(n,0) for n in names))
        put(s['event_fields'],dict(version=1,id=1,sequence=7,buffer_index=2,bytesused=len(payload),
            final_eoi=2,tail_length=12,first_packet=42,oldest_packet=42,newest_packet=42,
            packet_count=0 if missing else 1,copy_count=1),0)
        off=size['header']
        put(s['packet_fields'],dict(id=42,sequence=7,buffer_index=2,source_offset=2,copy_length=len(payload),
            actual_length=len(raw),decoded_header=2,header_present=1),off)
        off+=8*len(s['packet_fields'])
        for name in s['packet_arrays']:
            b=raw if name in ('raw_first','raw_last','boundary') else payload
            data[off:off+len(b)]=b;off+=64
        off=size['header']+s['ring']*size['packet']
        put(s['copy_fields'],dict(id=1,packet_id=42,sequence=7,buffer_index=2,source_offset=2,length=len(payload)),off)
        off+=8*len(s['copy_fields'])
        for name in s['copy_arrays']:
            b=payload if not corrupt or not name.startswith('source') else bytes(len(payload))
            data[off:off+len(b)]=b;off+=64
        data[size['frame']:]=payload
        return bytes(data)

    def test_exact_cross_layer_boundary_bytes(self):
        r,p=MODULE['decode'](self.fixture(),SCHEMA)
        self.assertEqual(r['evidence_gaps'],[])
        self.assertTrue(all(x['all_equal'] for x in r['correlation_segments']))
        self.assertEqual(r['classification'],'REQUIRES_CROSS_LAYER_REVIEW')
        self.assertEqual(r['tail_hex'],p[4:].hex())

    def test_missing_ring_is_gap_not_clean_layer(self):
        r,_=MODULE['decode'](self.fixture(missing=True),SCHEMA)
        self.assertEqual(r['classification'],'D')
        self.assertIn('source packet ring entry missing',r['evidence_gaps'])

    def test_async_disagreement_is_visible(self):
        r,_=MODULE['decode'](self.fixture(corrupt=True),SCHEMA)
        self.assertFalse(r['correlation_segments'][0]['all_equal'])

    def test_partial_output_rejected(self):
        with self.assertRaisesRegex(ValueError,'partial'):
            MODULE['decode'](self.fixture()[:-1],SCHEMA)
