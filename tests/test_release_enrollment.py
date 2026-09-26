"""Offline public enrollment boundaries; no image or physical media is written."""

from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "build/release"))
import enroll  # noqa: E402


class ReleaseEnrollmentTests(unittest.TestCase):
    def config(self, directory: Path, cidr: str = "192.0.2.0/24") -> Path:
        path = directory / "device.toml"
        path.write_text(
            '[network]\naddress="192.0.2.20/24"\n'
            f'admin_cidr="{cidr}"\nhostname="kvm.example.net"\n'
            '[auth]\nadmin_user="operator"\n'
            '[tls]\ncertificate="/tmp/example.crt"\nprivate_key="/tmp/example.key"\n'
            '[ssh]\n'
        )
        return path

    def test_public_admin_network_requires_explicit_opt_in(self):
        with tempfile.TemporaryDirectory() as temp:
            path = self.config(Path(temp), "0.0.0.0/0")
            with self.assertRaisesRegex(ValueError, "allow_public_admin"):
                enroll.config_data(path)
            path.write_text(path.read_text().replace('admin_cidr="0.0.0.0/0"',
                                                     'admin_cidr="0.0.0.0/0"\nallow_public_admin=true'))
            self.assertEqual(str(enroll.config_data(path)["allowed"]), "0.0.0.0/0")

    def test_password_file_mode_and_control_bytes(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "password"
            path.write_bytes(b"an-adequate-password\n")
            path.chmod(0o644)
            with self.assertRaisesRegex(ValueError, "0600"):
                enroll.password_bytes(path)
            path.chmod(0o600)
            self.assertEqual(enroll.password_bytes(path), b"an-adequate-password")
            path.write_bytes(b"password-with-tab\t")
            with self.assertRaisesRegex(ValueError, "control bytes"):
                enroll.password_bytes(path)

    def test_private_ssh_key_and_nonregular_image_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            private = directory / "id_ed25519"
            private.write_text("-----BEGIN OPENSSH PRIVATE KEY-----\nexample\n")
            with self.assertRaisesRegex(ValueError, "SSH public key"):
                enroll.ssh_material(private)
            image = directory / "base.img"
            image.write_bytes(b"regular image")
            link = directory / "base-link.img"
            link.symlink_to(image)
            with self.assertRaisesRegex(ValueError, "regular file"):
                enroll.regular(link)

    def test_tls_identity_must_match_host_and_ip(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            key, cert = directory / "server.key", directory / "server.crt"
            subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes",
                            "-keyout", str(key), "-out", str(cert), "-days", "2",
                            "-subj", "/CN=kvm.example.net",
                            "-addext", "subjectAltName=DNS:kvm.example.net,IP:192.0.2.20"],
                           check=True, capture_output=True)
            key.chmod(stat.S_IRUSR | stat.S_IWUSR)
            data = enroll.config_data(self.config(directory))
            data.update(cert=cert, key=key)
            enroll.supplied_tls(data)
            data["hostname"] = "wrong.example.net"
            with self.assertRaisesRegex(ValueError, "hostname mismatch"):
                enroll.supplied_tls(data)
            data["hostname"] = "kvm.example.net"
            data["address"] = enroll.ipaddress.ip_interface("192.0.2.21/24")
            with self.assertRaisesRegex(ValueError, "address mismatch"):
                enroll.supplied_tls(data)

    def test_tls_certificate_key_mismatch(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            cert_key, cert = directory / "matching.key", directory / "server.crt"
            other_key = directory / "other.key"
            subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes",
                            "-keyout", str(cert_key), "-out", str(cert), "-days", "2",
                            "-subj", "/CN=kvm.example.net",
                            "-addext", "subjectAltName=DNS:kvm.example.net,IP:192.0.2.20"],
                           check=True, capture_output=True)
            subprocess.run(["openssl", "genpkey", "-algorithm", "RSA", "-pkeyopt",
                            "rsa_keygen_bits:2048", "-out", str(other_key)],
                           check=True, capture_output=True)
            other_key.chmod(0o600)
            data = enroll.config_data(self.config(directory))
            data.update(cert=cert, key=other_key)
            with self.assertRaisesRegex(ValueError, "certificate/key mismatch"):
                enroll.supplied_tls(data)

    def test_network_replacement_stays_scoped_to_client_and_target(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            data = enroll.config_data(self.config(directory))
            cert, key = directory / "cert", directory / "key"
            cert.write_bytes(b"public-cert")
            key.write_bytes(b"private-key")
            data.update(cert=cert, key=key)
            def read_base(name: str) -> bytes:
                if name.endswith("nginx.conf"):
                    return (ROOT / "build/kvmd-lan/nginx.conf").read_bytes()
                return b"ListenAddress 192.168.88.2\nPasswordAuthentication no\n"
            values = enroll.replacements(data, b"test-password-long", read_base)
            nft = values["etc/kvmd/access.nft"][0]
            self.assertIn(b"ip saddr 192.0.2.0/24 ip daddr 192.0.2.20", nft)
            self.assertNotIn(b"192.168.88.1", nft)
            self.assertIn(b"policy drop", nft)
            self.assertNotIn(b"DHCP=yes", values["etc/systemd/network/10-lab.network"][0])
            self.assertNotIn("home/blikvm/.ssh/authorized_keys", values)


if __name__ == "__main__":
    unittest.main()
