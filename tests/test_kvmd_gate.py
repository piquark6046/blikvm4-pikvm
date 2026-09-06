import json
from pathlib import Path
import runpy
import tempfile
import unittest

AUDIT=runpy.run_path(str(Path(__file__).resolve().parents[1]/'lab/kvmd-gate.py'))['audit_api']
class KvmdEvidenceTests(unittest.TestCase):
    def fixture(self,p):
        value={'result':'passed','snapshots':[{'sha256':f'{i:064x}'} for i in range(12)],
               'websockets':[[{'event_type':e,'event':{'count':1}} for e in ('loop','streamer','clients','pong')] for _ in range(3)],
               'saved_state':{'snapshot':{'saved':{'online':True}}},
               'state_after':{'snapshot':{'saved':None}}}
        for i in range(11): (p/f'api-{i}.json').write_text(json.dumps(value))
        return value
    def test_rejects_missing_video_api_phase(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t);self.fixture(p);AUDIT(p);(p/'api-0.json').unlink()
            with self.assertRaisesRegex(ValueError,'coverage'): AUDIT(p)
    def test_rejects_frozen_snapshots_despite_claimed_pass(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t);v=self.fixture(p);v['snapshots']=[{'sha256':'0'*64}]*12
            (p/'api-0.json').write_text(json.dumps(v))
            with self.assertRaisesRegex(ValueError,'frozen'): AUDIT(p)
    def test_rejects_websocket_without_streamer_updates(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t);v=self.fixture(p);v['websockets'][0]=[{'event_type':'pong'}]
            (p/'api-0.json').write_text(json.dumps(v))
            with self.assertRaisesRegex(ValueError,'WebSocket'): AUDIT(p)
    def test_rejects_snapshot_state_not_cleared(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t);v=self.fixture(p);v['state_after']=v['saved_state']
            (p/'api-0.json').write_text(json.dumps(v))
            with self.assertRaisesRegex(ValueError,'state'): AUDIT(p)

class NoSignalEvidenceTests(unittest.TestCase):
    def test_accepts_native_pretty_json_and_static_snapshots(self):
        audit=runpy.run_path(str(Path(__file__).resolve().parents[1]/'lab/kvmd-gate.py'))['audit_no_signal']
        state={'result':{'streamer':{'source':{'online':True}}}}
        raw=json.dumps(state,indent=4)+'\n'+('a'*64+'  -\n')*4
        audit(raw)
        with self.assertRaisesRegex(ValueError,'static'):
            audit(raw.replace('a'*64,'b'*64,1))
        with self.assertRaisesRegex(ValueError,'availability'):
            audit(raw.replace('true','false'))
