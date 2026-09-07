import json
from pathlib import Path
import runpy
import tempfile
import unittest

stream=runpy.run_path(str(Path(__file__).resolve().parents[1]/'lab/lan-acceptance-gate.py'))['stream']


class LanGateTests(unittest.TestCase):
    def fixture(self,root,frames=3240):
        records=[{'t':round((i+1)*120/frames,6),'bytes':100,'sha256':f'{i:064x}'} for i in range(frames)]
        (root/'frames.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in records))
        (root/'result.json').write_text(json.dumps({'result':'passed','seconds_requested':120,
            'elapsed':120,'frames':frames,'bytes':frames*100,'unique_hashes':frames}))
        return records

    def test_exact_gate_is_not_lowered_to_m8b_diagnostic(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);self.fixture(root)
            self.assertEqual(stream(root)['fps'],27)
            self.fixture(root,3237)
            with self.assertRaises(AssertionError):stream(root)

    def test_replay_rejects_missing_frames_despite_pass_flag(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);records=self.fixture(root)
            (root/'frames.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in records[:-1]))
            with self.assertRaises(AssertionError):stream(root)

    def test_replay_rejects_long_gap_despite_sufficient_total(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);records=self.fixture(root)
            for r in records:
                if 50 <= r['t'] < 54:r['t']=54
            (root/'frames.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in records))
            with self.assertRaises(AssertionError):stream(root)
