"""Media delegate rejects capability expansion before performing configfs writes."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

P = Path(__file__).resolve().parents[1]/'build/kvmd-msd/media-helper.py'
spec=importlib.util.spec_from_file_location('media_helper',P)
M=importlib.util.module_from_spec(spec);spec.loader.exec_module(M)


class MediaRequests(unittest.TestCase):
    def request(self, **kwargs):
        return dict(operation='attach',gadget='blikvm_m5',function='mass_storage.g4',lun='lun.0',image='g4-storage.img',**kwargs)

    def test_invalid_requests_never_reach_configfs(self):
        invalid=[None, [], {}, {'operation':'reset'}]
        for key,value in [('gadget','other'),('function','mass_storage.usb0'),('lun','lun.1'),('operation','write')]:
            req=self.request();req[key]=value;invalid.append(req)
        for key in ('rw','cdrom','path','command'):
            req=self.request();req[key]=True;invalid.append(req)
        with patch.object(M,'validate') as validate:
            for req in invalid:
                with self.subTest(req=req),self.assertRaises(ValueError):M.operate(req)
            validate.assert_not_called()

    def test_paths_and_unknown_images_cannot_write(self):
        with tempfile.TemporaryDirectory() as d:
            lun=Path(d);(lun/'file').write_text('')
            for name in ('../g4-storage.img','/dev/mmcblk0','/etc/passwd','other.img',None,[]):
                req=self.request();req['image']=name
                with patch.object(M,'validate',return_value=lun),patch.object(M,'catalog',return_value={'g4-storage.img':{}}):
                    with self.subTest(name=name),self.assertRaises(ValueError):M.operate(req)
                self.assertEqual((lun/'file').read_text(),'')
                self.assertFalse((lun/'forced_eject').exists())

    def test_attach_only_changes_file(self):
        with tempfile.TemporaryDirectory() as d:
            lun=Path(d);(lun/'file').write_text('')
            with patch.object(M,'validate',return_value=lun),patch.object(M,'catalog',return_value={'g4-storage.img':{}}):
                self.assertEqual(M.operate(self.request()),{'ok':True})
            self.assertEqual((lun/'file').read_text(),str(M.ROOT/'g4-storage.img')+'\n')
            self.assertEqual({p.name for p in lun.iterdir()},{'file'})

    def test_unapproved_current_medium_cannot_be_ejected(self):
        with tempfile.TemporaryDirectory() as d:
            lun=Path(d);(lun/'file').write_text('/dev/mmcblk0\n')
            req=self.request();req.pop('image');req['operation']='eject'
            with patch.object(M,'validate',return_value=lun),patch.object(M,'catalog',return_value={'g4-storage.img':{}}):
                with self.assertRaises(ValueError):M.operate(req)
            self.assertFalse((lun/'forced_eject').exists())

    def test_symlink_catalog_is_refused(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'image';path.symlink_to('/etc/passwd')
            with self.assertRaises(ValueError):M.secure_path(path)

    def test_world_writable_parent_is_refused(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'image';path.write_text('x')
            with self.assertRaises(ValueError):M.secure_path(path)


if __name__=='__main__':unittest.main()
