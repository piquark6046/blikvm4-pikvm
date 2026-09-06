import hashlib
from pathlib import Path
import runpy
import struct
import tempfile
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
G4=runpy.run_path(str(ROOT/'lab/storagelab.py'))

class StorageTests(unittest.TestCase):
    def test_image_geometry_and_files_independent_decode(self):
        image=G4['IMAGE']['build_image']()
        self.assertEqual(len(image),8388608)
        self.assertEqual(image[510:512],b'\x55\xaa')
        bps,spc,res,nfats,entries,sectors,media,spf=struct.unpack_from('<HBHBHHBH',image,11)
        self.assertEqual((bps,spc,res,nfats,entries,sectors,spf),(512,2,1,2,512,16384,32))
        self.assertEqual(image[512:33*512],image[33*512:65*512])
        root=(res+nfats*spf)*bps
        start=root+entries*32
        found={}
        for offset in range(root,root+entries*32,32):
            e=image[offset:offset+32]
            if e[0]==0:break
            if e[11]==8:continue
            name=e[:8].decode().strip()+'.'+e[8:11].decode().strip()
            cluster,size=struct.unpack_from('<HI',e,26)
            self.assertEqual(struct.unpack_from('<H',image,bps+cluster*2)[0],0xffff)
            found[name]=image[start+(cluster-2)*spc*bps:start+(cluster-2)*spc*bps+size]
        self.assertEqual(found,G4['IMAGE']['FILES'])
        self.assertEqual(hashlib.sha256(image).hexdigest(),G4['EXPECTED']['sha256'])
        self.assertEqual(image,G4['IMAGE']['build_image']())

    def test_exact_composite_required(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);device=root/'1-3';device.mkdir()
            (device/'speed').write_text('480');(device/'descriptors').write_bytes(b'test')
            for i,(c,s,p,d) in enumerate([('03','01','01','usbhid'),('03','00','00','usbhid'),('03','00','00','usbhid'),('08','06','50','usb-storage')]):
                f=root/f'1-3:1.{i}';f.mkdir()
                for n,v in [('bInterfaceClass',c),('bInterfaceSubClass',s),('bInterfaceProtocol',p)]: (f/n).write_text(v)
                (f/'driver').symlink_to('/drivers/'+d)
            self.assertTrue(G4['details'](device)['passed'])
            (root/'1-3:1.3/driver').unlink()
            self.assertFalse(G4['details'](device)['passed'])
            (root/'1-3:1.3/driver').symlink_to('/drivers/usb-storage')
            (root/'1-3:1.4').mkdir()
            self.assertFalse(G4['details'](device)['passed'])

    def test_extra_target_function_rejected(self):
        text='functions_begin\nhid.absolute hid.keyboard hid.relative mass_storage.g4\nfunctions_end'
        self.assertTrue(G4['valid_functions'](text))
        self.assertFalse(G4['valid_functions'](text.replace('mass_storage.g4','mass_storage.g4 mass_storage.extra')))

    def test_hid_generators_are_frozen(self):
        for name in ('mouse_command','relative_command','concurrent_command','concurrent_setup_commands'):
            self.assertEqual(G4[name](),G4['G3'][name]())
        self.assertLess(len(G4['mapping_command'](True)),1800)

    def test_direct_read_uses_aligned_uncached_io(self):
        import os
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'image';p.write_bytes(G4['IMAGE']['build_image']())
            self.assertEqual(G4['read_image_direct'](str(p)),p.read_bytes())

    def test_storage_requires_expected_topology_readonly_capacity_and_inquiry(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);device=root/'usb/1-3';device.mkdir(parents=True)
            interface=root/'usb/1-3:1.3';scsi=interface/'host1/target1/1:0:0:0'
            disk=scsi/'block/sdz';disk.mkdir(parents=True)
            (disk/'device').symlink_to(scsi)
            (scsi/'scsi_generic/sg7').mkdir(parents=True)
            (scsi/'driver').symlink_to('/drivers/sd')
            for n,v in [('vendor','BliKVM'),('model','G4 RAM RO'),('rev','0001'),('type','0')]:
                (scsi/n).write_text(v)
            for n,v in [('dev','8:240'),('ro','1'),('size','16384'),('queue/logical_block_size','512')]:
                p=disk/n;p.parent.mkdir(exist_ok=True);p.write_text(v)
            blocks=root/'blocks';blocks.mkdir();(blocks/'sdz').symlink_to(disk)
            dev=root/'dev';dev.mkdir();(dev/'sdz').touch()
            def path(value):
                if str(value)=='/sys/class/block':return blocks
                if str(value).startswith('/dev/'):return dev/Path(value).name
                return Path(value)
            fn=G4['block_identity']
            with patch.dict(fn.__globals__,Path=path):
                record=fn(device,timeout=.2)
                self.assertEqual(record['node'],'/dev/sdz')
                self.assertEqual(record['sg'],'/dev/sg7')
                (disk/'ro').write_text('0')
                with self.assertRaises(RuntimeError):fn(device,timeout=.01)
                (disk/'ro').write_text('1');(scsi/'model').write_text('valuable disk')
                with self.assertRaises(RuntimeError):fn(device,timeout=.1)

    def test_concurrent_pool_is_not_shadowed_by_boolean_argument(self):
        import ast
        tree=ast.parse((ROOT/'lab/storagelab.py').read_text())
        calls=[n for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='ThreadPoolExecutor']
        self.assertTrue(calls)
        with G4['ThreadPoolExecutor'](max_workers=1) as pool:
            self.assertEqual(pool.submit(lambda: 42).result(),42)

    def test_unexpected_usb_reset_rejects_false_positive_pass(self):
        reset='2026-09-06 usb 1-3: reset high-speed USB device number 50 using xhci_hcd'
        normal='sd 1:0:0:0: Power-on or device reset occurred'
        self.assertEqual(G4['unexpected_resets'](normal+'\n'+reset),[reset])
