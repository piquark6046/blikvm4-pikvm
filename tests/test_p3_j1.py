"""Causal classifier adversarial fixtures; entirely offline."""
import json
from pathlib import Path
import runpy
import unittest

ROOT=Path(__file__).resolve().parents[1]
V=runpy.run_path(str(ROOT/'research/evidence/p3/j1/verify.py'))
FIXTURES=json.loads((ROOT/'research/evidence/p3/j1/fixtures.json').read_text())


class CausalJournal(unittest.TestCase):
    def test_independent_adversarial_fixtures(self):
        for fixture in FIXTURES:
            with self.subTest(case=fixture['name']):
                result=V['compare'](fixture['journal'],offline=fixture.get('offline',False))
                self.assertEqual(result['result']=='JOURNAL_ELIGIBLE',fixture['expected_eligible'])
                self.assertEqual(result['qualification_credit'],0)

    def test_functional_gates_are_mandatory(self):
        rows=FIXTURES[1]['journal']
        for missing in ('https_passed','auth_passed','core_passed','generations_unchanged'):
            gates=dict(https_passed=True,auth_passed=True,core_passed=True,generations_unchanged=True)
            gates[missing]=False
            with self.subTest(gate=missing),self.assertRaises(ValueError):
                V['C']['require_qualification'](rows,**gates)

    def test_no_replacement_time_cutoff(self):
        original=V['C']['classify'](FIXTURES[1]['journal'])
        shifted=V['C']['classify'](next(f['journal'] for f in FIXTURES if f['name']=='positive-time-translation'))
        self.assertEqual(original['result'],shifted['result'])
        self.assertEqual([r['classification'] for r in original['records']],
                         [r['classification'] for r in shifted['records']])


if __name__=='__main__':unittest.main()
