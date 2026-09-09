"""Native boundary tests compile the actual candidate helper from its patch."""
from pathlib import Path
import json
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]

class MS2131CandidateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory();root=Path(cls.tmp.name)
        patch=(ROOT/'build/linux-candidates/ms2131-bulk-eof-reject.patch').read_text()
        added='\n'.join(x[1:] for x in patch.splitlines() if x.startswith('+') and not x.startswith('+++'))
        start=added.index('static bool uvc_video_ms2131_bad_eof(')
        helper=added[start:added.index('\n}',start)+2]
        code='''#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
typedef unsigned char u8;
#define JPEG_MARKER_EOI 0xd9
#define UVC_STREAM_EOF 2
'''+helper+'''
int main(int argc,char **argv) {
 unsigned char data[20000];size_t n=fread(data,1,sizeof(data),stdin);
 if(argc!=4)return 2;
 printf("%d\\n",uvc_video_ms2131_bad_eof(data,n,atoi(argv[1]),atoi(argv[2]),atoi(argv[3])));
 return 0;
}
'''
        src=root/'test.c';src.write_text(code);cls.binary=root/'test'
        subprocess.run(['cc','-Wall','-Wextra','-Werror','-fsanitize=undefined','-o',str(cls.binary),str(src)],check=True)

    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()

    def check(self,body,expected,requested=15360,maximum=15360,packet=512):
        r=subprocess.run([str(self.binary),str(requested),str(maximum),str(packet)],input=body,capture_output=True,check=True)
        self.assertEqual(r.stderr,b'');self.assertEqual(r.stdout.strip(),str(int(expected)).encode())

    def faulty(self):
        row=json.loads((ROOT/'research/evidence/m8f0/uvc-diag-02/observation05-vm-audit.json').read_text())['records'][0]
        packet=row['tail_packet'];body=bytearray(packet['actual_length'])
        body[:64]=bytes.fromhex(packet['raw_first']);body[-64:]=bytes.fromhex(packet['raw_last'])
        return body

    def test_observed_framing_is_rejected(self):self.check(self.faulty(),True)

    def test_zero_sof_suffix_is_also_rejected(self):
        # This trailer can pass the accepted userspace end-marker heuristic.
        b=self.faulty();b[-2:]=b'\x00\x00';self.check(b,True)

    def test_ordinary_payload_and_separate_eof_are_unchanged(self):
        b=self.faulty();self.check(b[:-12],False);self.check(b[-12:],False)

    def test_header_like_suffix_alone_is_insufficient(self):
        b=self.faulty()
        for offset in (-14,-13,-12,-11,-10,-9,-8,-7):
            with self.subTest(offset=offset):
                changed=b.copy();changed[offset]^=1;self.check(changed,False)
        b=self.faulty();b[-1]|=0x80;self.check(b,False)

    def test_transport_boundary_is_required(self):
        b=self.faulty();self.check(b,False,packet=1024)
        self.check(b,False,requested=len(b));self.check(b,False,maximum=len(b))
        self.check(b[:100]+b'X'+b[100:],False)

    def test_truncations_and_nonstandard_headers_are_safe(self):
        b=self.faulty()
        for length in (0,1,11,12,13,511,512,525):self.check(b[:length],False)
        for flags in (0x8e,0x8f,0xcc,0x80,0x0c):
            b=self.faulty();b[1]=flags;self.check(b,False)
        b=self.faulty();b[0]=2;self.check(b,False)
