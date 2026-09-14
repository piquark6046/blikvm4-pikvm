import json
from pathlib import Path
import runpy
import tempfile
import unittest
from types import SimpleNamespace

R = runpy.run_path(str(Path(__file__).resolve().parents[1]/'lab/p3-publication-rehearsal.py'))


class PublicationLifecycle(unittest.TestCase):
    def test_source_sites(self):
        R['source_sites'](R['NEW'])

    def test_frozen_old_bug(self):
        with tempfile.TemporaryDirectory() as d:
            report = R['exercise'](Path(d)/'old', 'success', R['OLD'])
            R['check_report'](report, old=True)

    def test_complete_paths(self):
        for case in R['CASES']:
            with self.subTest(case=case), tempfile.TemporaryDirectory() as d:
                root = Path(d)/'case'
                report = R['exercise'](root, case)
                R['check_report'](report)
                cycle = root/'controller/p3-a03-cycle-001'
                declaration = json.loads((cycle/'cycle.json').read_text())
                self.assertEqual(declaration['record'], 'immutable_cycle_declaration')
                self.assertNotIn('result', declaration)
                final = cycle/'cycle-final.json'; result = cycle/'result.json'
                if case == 'success':
                    self.assertEqual(json.loads(final.read_text())['result'], 'CYCLE_PASS_PENDING_INDEPENDENT_REPLAY')
                    self.assertEqual(json.loads(result.read_text())['result'], 'FUNCTIONAL_PASS_PENDING_VM_REPLAY')
                else:
                    latch = json.loads((root/'controller/P3_A03_FAILED.json').read_text())
                    self.assertEqual(latch['result'], 'FAILED')
                    self.assertEqual(latch['accepted_cycles'], 0)

    def test_prestart_runtime_and_input_drift_stop_before_target(self):
        source = R['ROOT']/'lab/p3-a03-prestart.py'
        for drift in ('runtime', 'input'):
            with self.subTest(drift=drift), tempfile.TemporaryDirectory() as d:
                root = Path(d); (root/'controller').mkdir()
                records = {}; calls = []
                def read(path):
                    if path.name == 'source-provenance.json':
                        return dict(clean=True, commit='a'*40, origin_main='a'*40, files={})
                    if path.name.endswith('-replay.json'):
                        return dict(result='CONTROLLER_R1_REHEARSAL_INDEPENDENTLY_REPLAYED', qualification_credit=0, old_bug_reproduced=True)
                    if path.name == 'h5r2-acceptance.json': return dict(result='H5R2_INDEPENDENTLY_ACCEPTED')
                    if path.name == 'contract.json': return dict(runtime_manifest={})
                    if path.name == 'functional-input-manifest.json': return {}
                    raise AssertionError(path)
                p = dict(read=read, publish=lambda path, value: records.setdefault(str(path), value),
                         mkdir=lambda path: path.mkdir(), idle=lambda: None, RUNTIME=root/'runtime',
                         manifest=lambda path: {'changed': True} if path == root/drift else {})
                f = dict(P=p, BASE=root, collect=lambda *args: calls.append('target'))
                g = dict(__file__=str(source), Path=Path,
                         os=SimpleNamespace(geteuid=lambda: 0, umask=lambda _: None),
                         runpy=SimpleNamespace(run_path=lambda _: f))
                R['load_functions'](source, g)
                with self.assertRaisesRegex(RuntimeError, 'H5R2 .* changed'): g['main']()
                self.assertEqual(calls, [])
                self.assertEqual(len(records), 1)
                self.assertEqual(records[str(root/'controller/P3_A03_FAILED.json')]['result'], 'FAILED')


if __name__ == '__main__': unittest.main()
