import json
from pathlib import Path
import runpy
import tempfile
import unittest

AUDIT=runpy.run_path(str(Path(__file__).resolve().parents[1]/'lab/ustreamer-gate.py'))['audit_stream']


class StreamAuditTests(unittest.TestCase):
    def fixture(self, root, frozen=False, gap=False):
        rows=[dict(t=(i+1)/6,bytes=100,sha256=f'{0 if frozen else i:064x}') for i in range(30)]
        if gap:
            for r in rows[:24]: r['t']=.1
        summary=dict(result='passed',seconds_requested=5,elapsed=5.1,frames=30,bytes=3000,
                     unique_hashes=len({r['sha256'] for r in rows}),transitions=0 if frozen else 29)
        (root/'frames.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
        (root/'result.json').write_text(json.dumps(summary))

    def test_recomputes_counts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);self.fixture(root)
            self.assertEqual(AUDIT(root)['frames'],30)
            p=root/'result.json';s=json.loads(p.read_text());s['frames']=31;p.write_text(json.dumps(s))
            with self.assertRaises(ValueError): AUDIT(root)

    def test_rejects_claimed_pass_for_frozen_or_stalled_stream(self):
        for options in ({'frozen':True},{'gap':True}):
            with tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);self.fixture(root,**options)
                with self.assertRaises(ValueError): AUDIT(root)

class ModeAuditTests(unittest.TestCase):
    def test_rejects_device_maximum_even_with_thirty_fps_delivery(self):
        from unittest.mock import patch
        audit=runpy.run_path(str(Path(__file__).resolve().parents[1]/'lab/ustreamer-gate.py'))['audit_run']
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            result=dict(result='passed',stage='ustreamer_qualification',restarts=[{}]*6,
                        signal_cycles=[dict(automatic=True,pid='17',recovery={'result':'passed'})]*3,
                        storage={'passed':True},concurrent_storage={'passed':True},
                        hid={k:{'passed':True} for k in ('keyboard','absolute','relative')},usb_errors=[])
            (root/'test-results.json').write_text(json.dumps(result))
            (root/'negotiated-after.log').write_text("Width/Height: 1920/1080\nPixel Format: 'MJPG'\nFrames per second: 50.000 (50/1)\n")
            with patch.dict(audit.__globals__,audit_stream=lambda _:dict(frames=3600,seconds_requested=120)):
                with self.assertRaisesRegex(ValueError,'negotiated mode mismatch'):
                    audit(root)
