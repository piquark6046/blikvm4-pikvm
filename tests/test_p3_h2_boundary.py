import json
import os
from pathlib import Path
import runpy
import tempfile
import unittest

B = runpy.run_path(str(Path(__file__).resolve().parents[1]/'lab/p3-h2-boundary.py'))


class BoundaryTests(unittest.TestCase):
    def test_browser_symlink_cannot_redirect_read_or_controller_publication(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            protected = root/'protected'
            protected.write_text('{"unchanged":true}')
            (root/'browser-result.json').symlink_to(protected)
            with self.assertRaises(OSError):
                B['read_json'](root/'browser-result.json')
            with self.assertRaises(FileExistsError):
                B['publish'](root/'browser-result.json', {'bad': True})
            self.assertEqual(protected.read_text(), '{"unchanged":true}')

    def test_substituted_ancestor_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root/'real').mkdir()
            (root/'leaf').symlink_to(root/'real', target_is_directory=True)
            with self.assertRaises(OSError):
                B['publish'](root/'leaf'/'control.json', {})
            self.assertEqual(list((root/'real').iterdir()), [])

    def test_archive_input_rejects_hardlinks_symlinks_and_fifos(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            f = root/'file'
            f.write_text('original')
            for kind in ('hardlink', 'symlink', 'fifo'):
                other = root/'other'
                if kind == 'hardlink': os.link(f, other)
                elif kind == 'symlink': other.symlink_to(f)
                else: os.mkfifo(other)
                with self.assertRaises(RuntimeError): B['tree'](root)
                other.unlink()

    def test_publication_does_not_replace_existing_control(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)/'ack'
            B['publish'](p, {'result': 'passed'}, 0o644)
            with self.assertRaises(FileExistsError):
                B['publish'](p, {'result': 'failed'})
            self.assertEqual(B['read_json'](p), {'result': 'passed'})

    def test_unexpected_acl_rejected(self):
        import struct
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)/'acl'
            p.touch()
            # Linux POSIX ACL: owner, named uid, group, mask, other.
            data = struct.pack('<I', 2)+b''.join(struct.pack('<HHI', *e) for e in
                [(1,6,0xffffffff),(2,4,12345),(4,0,0xffffffff),
                 (16,4,0xffffffff),(32,0,0xffffffff)])
            try:
                os.setxattr(p, 'system.posix_acl_access', data)
            except OSError as e:
                if e.errno in (22, 95):
                    self.skipTest('filesystem does not support this POSIX ACL fixture')
                raise
            with self.assertRaisesRegex(RuntimeError, 'unexpected ACL'):
                B['no_acl'](p)
