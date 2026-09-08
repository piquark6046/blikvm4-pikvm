import runpy
from pathlib import Path
import unittest
import subprocess

M = runpy.run_path(str(Path(__file__).resolve().parents[1]/'lab/verify-core-soak.py'))


class SoakGateTests(unittest.TestCase):
    def test_browser_error_logs_do_not_expose_sessions(self):
        source = (Path(__file__).resolve().parents[1]/'lab/soak-browser.mjs').read_text()
        snippet = 'const scrub='+source.split('const scrub=', 1)[1].split('const write=', 1)[0]
        script = "const credentials={passwd:'synthetic-password'};"+snippet+"""
const assert=require('node:assert/strict');
const value=encode({error:'Call log:\\n - cookie: auth_token=synthetic-session\\n - passwd=synthetic-password',
                   nested:['Set-Cookie: auth_token=another-session; Secure']});
assert(!value.includes('synthetic-session'));
assert(!value.includes('another-session'));
assert(!value.includes('synthetic-password'));
assert(!/cookie:/i.test(value));
assert(value.includes('Call log:'));
"""
        subprocess.run(['node', '-e', script], check=True, capture_output=True, text=True)

    def test_pilot_and_short_run_cannot_pass(self):
        r = {'qualification': 'M8-F', 'required_seconds': 86400,
             'result': 'completed_pending_independent_review', 'start_monotonic': 100,
             'end_monotonic': 86500}
        self.assertTrue(M['duration_gate'](r))
        self.assertFalse(M['duration_gate']({**r, 'end_monotonic': 86499.99}))
        self.assertFalse(M['duration_gate']({**r, 'qualification': 'pilot'}))
        self.assertFalse(M['duration_gate']({**r, 'result': 'failed'}))

    def test_event_exclusion_has_exact_bounds(self):
        events = [{'start': 10, 'until': 70}]
        self.assertFalse(M['intersects'](0, 10, events))
        self.assertTrue(M['intersects'](9, 11, events))
        self.assertFalse(M['intersects'](70, 75, events))

    def test_monotonic_growth_remains_visible(self):
        t = M['trend']([100, 101, 102, 103, 104, 105, 106, 107])
        self.assertTrue(t['monotonic_nondecreasing'])
        self.assertGreater(t['delta'], 0)
        self.assertFalse(M['trend']([100, 101, 100, 100])['monotonic_nondecreasing'])
