import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('binfmt_rule', ROOT / 'build/ubuntu/binfmt-rule.py')
RULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RULE)


class EmulationRuleTests(unittest.TestCase):
    def test_architecture_match_rejects_native_and_other_elf(self):
        for machine in (3, 40, 62, 243):
            header = bytearray(RULE.MAGIC)
            header[18:20] = machine.to_bytes(2, 'little')
            self.assertFalse(RULE.matches(header))
        for elf_type in (2, 3):
            header = bytearray(RULE.MAGIC)
            header[16:18] = elf_type.to_bytes(2, 'little')
            self.assertTrue(RULE.matches(header))
        self.assertFalse(RULE.matches(b'#!/bin/sh\n'))
        self.assertFalse(RULE.matches(Path('/bin/sh').read_bytes()[:20]))

    def test_kernel_registration_has_no_raw_nuls(self):
        encoded = RULE.rule('/bin/sh')
        self.assertNotIn('\0', encoded)
        fields = encoded.split(':')
        self.assertEqual(len(fields), 8)
        self.assertEqual(bytes.fromhex(fields[4].replace('\\x', '')), RULE.MAGIC)
        self.assertEqual(bytes.fromhex(fields[5].replace('\\x', '')), RULE.MASK)
        self.assertEqual(len(RULE.MAGIC), 20)
        self.assertEqual(len(RULE.MASK), 20)
