import json
import os
from pathlib import Path
import runpy
import tempfile
import unittest

H=runpy.run_path(str(Path(__file__).resolve().parents[1]/'lab/p3-h3-boundary.py'))


class H3PathTests(unittest.TestCase):
    def test_browser_symlink_rejected_without_touching_destination(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);leaf=root/'active';leaf.mkdir();secret=root/'protected';secret.write_text('unchanged')
            (leaf/'result.json').symlink_to(secret)
            with self.assertRaisesRegex(RuntimeError,'symlink output'):
                H['manifest'](leaf)
            with self.assertRaises(OSError):H['read_json'](leaf/'result.json')
            self.assertEqual(secret.read_text(),'unchanged')

    def test_complete_legacy_manifest_preserves_unknown_world_writable_descendant(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);leaf=root/'unknown'/'deeper';leaf.mkdir(parents=True);leaf.chmod(0o777)
            probe=leaf/'h2-probe';probe.touch()
            (root/'link').symlink_to('/nonexistent')
            m=H['manifest'](root,legacy=True)
            self.assertEqual(m[str(leaf)]['mode'],0o777)
            self.assertEqual(m[str(probe)]['size'],0)
            self.assertEqual(m[str(root/'link')]['link'],'/nonexistent')

    def test_hardlink_and_fifo_outputs_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);a=root/'a';a.write_text('x');os.link(a,root/'b')
            with self.assertRaisesRegex(RuntimeError,'hardlinked'):H['manifest'](root)
            (root/'b').unlink();os.mkfifo(root/'fifo')
            with self.assertRaisesRegex(RuntimeError,'special'):H['manifest'](root)

    def test_controller_publish_is_exclusive_and_rejects_parent_symlink(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);dest=root/'dest';dest.mkdir(mode=0o700);alias=root/'alias';alias.symlink_to(dest)
            H['publish'](dest/'record',{'original':True})
            with self.assertRaises(FileExistsError):H['publish'](dest/'record',{'overwrite':True})
            with self.assertRaises(OSError):H['publish'](alias/'escape',{})
            self.assertEqual(json.loads((dest/'record').read_text()),{'original':True})
            self.assertFalse((dest/'escape').exists())


if __name__=='__main__':unittest.main()
