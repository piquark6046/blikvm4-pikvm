"""Exact package notice coverage and rootfs license-document integrity."""

from pathlib import Path
import sys
import tarfile
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "build/release"))
import notices  # noqa: E402


class ReleaseNoticesTests(unittest.TestCase):
    def test_checked_in_notice_lock_covers_frozen_package_inventory(self):
        notices.verify_inventory_lock(ROOT / "build/kvmd-msd/packages.lock.tsv",
                                      ROOT / "release/package-notices.tsv")

    def test_rootfs_license_documents_and_link_are_verified(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            rootfs = base / "rootfs"
            docs = rootfs / "usr/share/doc"
            (docs / "libexample").mkdir(parents=True)
            (docs / "libexample/copyright").write_text("License: MIT\n")
            (docs / "example").symlink_to("libexample")
            status = rootfs / "var/lib/dpkg/status"
            status.parent.mkdir(parents=True)
            status.write_text("Package: example\nStatus: install ok installed\nVersion: 1\n"
                              "Architecture: arm64\nSource: example-src (1)\n\n")
            inventory = base / "packages.tsv"
            inventory.write_text("example\t1\tarm64\n")
            archive = base / "rootfs.tar.gz"
            with tarfile.open(archive, "w:gz") as tar:
                tar.add(rootfs, arcname=".")
            lock = base / "package-notices.tsv"
            lock.write_text(notices.HEADER + "\n" + "\n".join(notices.rows(inventory, archive)) + "\n")
            notices.verify(inventory, archive, lock)
            self.assertIn("example-src (1)", lock.read_text())
            lock.write_text(lock.read_text().replace("MIT", "GPL-2+"))
            with self.assertRaisesRegex(ValueError, "differs from exact rootfs"):
                notices.verify(inventory, archive, lock)
            (docs / "libexample/copyright").unlink()
            with self.assertRaisesRegex(ValueError, "missing installed license document"):
                notices.rows(inventory, rootfs)

    def test_new_package_without_notice_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            inventory = Path(temp) / "packages.tsv"
            inventory.write_text("unexpected\t1\tarm64\n")
            with self.assertRaisesRegex(ValueError, "count differs"):
                notices.verify_inventory_lock(inventory, ROOT / "release/package-notices.tsv")


if __name__ == "__main__":
    unittest.main()
