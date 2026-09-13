"""Negative offline gates; never attach a device or assemble an image."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
def load(name, filename):
    spec=importlib.util.spec_from_file_location(name,ROOT/'build/image'/filename)
    module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module

A=load('p1','assemble.py')
V=load('vendor','verify-vendor.py')
S=load('separation','verify-enrollment-separation.py')

class ImageProductionTests(unittest.TestCase):
    def test_standalone_revision_rejects_network_drift(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); p=root/A.NETWORK_PATH; p.parent.mkdir(parents=True)
            p.write_bytes(A.P1_NETWORK+b'DHCP=yes\n')
            with self.assertRaisesRegex(AssertionError, 'network input drift'):
                A.standalone_network(root, 'p2-r1-candidate1')
            p.write_bytes(A.P1_NETWORK)
            A.standalone_network(root, 'p1')
            self.assertEqual(p.read_bytes(), A.P1_NETWORK)
            A.standalone_network(root, 'p2-r1-candidate1')
            self.assertEqual(p.read_bytes().replace(b'ConfigureWithoutCarrier=yes\n',b''), A.P1_NETWORK)

    def test_enrollment_bytes_rejected_outside_filesystem(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); enrollment=root/'enrollment';enrollment.mkdir()
            secret=b'private-test-payload-not-a-real-credential-0123456789'
            (enrollment/'payload').write_bytes(secret)
            (enrollment/'provenance.json').write_text(json.dumps({'files':{'payload':{'sha256':hashlib.sha256(secret).hexdigest()}}}))
            image=root/'image';image.write_bytes(bytes(4096)+secret+bytes(4096))
            with self.assertRaisesRegex(AssertionError,'private enrollment'):
                S.verify([image],enrollment)
            image.write_bytes(bytes(8192))
            self.assertEqual(S.verify([image],enrollment)['result'],'passed')

    def test_unknown_ssha512_rejected_in_raw_bytes(self):
        import base64
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); enrollment=root/'enrollment';enrollment.mkdir()
            (enrollment/'provenance.json').write_text('{"files":{}}')
            image=root/'image';image.write_bytes(bytes(512)+b'{SSHA512}'+base64.b64encode(bytes(range(80))))
            with self.assertRaisesRegex(AssertionError,'SSHA512'):
                S.verify([image],enrollment)

    def test_mbr_no_old_partition_or_boot_prefix(self):
        b=A.mbr()
        self.assertEqual(len(b),512)
        self.assertEqual(b[:440],bytes(440))
        self.assertEqual(b[462:510],bytes(48))
        self.assertEqual(b[510:],b'\x55\xaa')

    def test_private_material_rejected_in_raw_unallocated_area(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/'root';root.mkdir();image=Path(d)/'image'
            image.write_bytes(b'\0'*300+b'-----BEGIN PRIVATE KEY-----\n'+b'A'*80+b'\n')
            with self.assertRaisesRegex(ValueError,'raw image'):
                A.secret_scan(root,image)

    def test_development_authorization_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/'root';p=root/'home/blikvm/.ssh/authorized_keys';p.parent.mkdir(parents=True)
            p.write_text('ssh-ed25519 public-but-user-specific-key\n')
            image=Path(d)/'image';image.write_bytes(bytes(512))
            with self.assertRaisesRegex(ValueError,'nonempty enrollment'):
                A.secret_scan(root,image)

    def test_empty_password_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/'root';(root/'etc').mkdir(parents=True)
            (root/'etc/shadow').write_text('root::20000:0:99999:7:::\n')
            image=Path(d)/'image';image.write_bytes(bytes(512))
            with self.assertRaisesRegex(ValueError,'unlocked'):
                A.secret_scan(root,image)

    def test_script_crc_and_command_must_match(self):
        with tempfile.TemporaryDirectory() as d:
            cmd=Path(d)/'boot.cmd';scr=Path(d)/'boot.scr';cmd.write_bytes((A.HERE/'boot.cmd').read_bytes())
            A.run(['mkimage','-A','arm','-O','linux','-T','script','-C','none','-n','test','-d',cmd,scr])
            A.verify_script(scr,cmd)
            b=bytearray(scr.read_bytes());b[-10]^=1;scr.write_bytes(b)
            with self.assertRaises(AssertionError):A.verify_script(scr,cmd)

    @unittest.skipUnless((ROOT/'out/p1/vendor/prefix-4MiB.bin').exists(),'private capture unavailable')
    def test_vendor_corruption_fails_even_with_updated_outer_hash(self):
        layout=json.loads((ROOT/'research/evidence/p1/vendor-layout.json').read_text())
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'prefix';b=bytearray((ROOT/'out/p1/vendor/prefix-4MiB.bin').read_bytes())
            b[9000]^=1;p.write_bytes(b)
            layout['source_prefix_sha256']=hashlib.sha256(b).hexdigest()
            with self.assertRaises(AssertionError):V.verify(p,layout)

if __name__=='__main__':unittest.main()
