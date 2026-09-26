"""Release inputs must not carry build-host resolver state."""

import importlib.util
import io
from pathlib import Path
import tarfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "build/release/make-input-lock.py"
SPEC = importlib.util.spec_from_file_location("release_input_lock", SOURCE)
INPUT_LOCK = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(INPUT_LOCK)


class ReleaseInputLockTests(unittest.TestCase):
    def archive(self, names: tuple[str, ...]) -> tarfile.TarFile:
        stream = io.BytesIO()
        with tarfile.open(fileobj=stream, mode="w") as archive:
            for name in names:
                payload = b"fixture\n"
                member = tarfile.TarInfo(name)
                member.size = len(payload)
                archive.addfile(member, io.BytesIO(payload))
        stream.seek(0)
        return tarfile.open(fileobj=stream, mode="r")

    def test_rejects_builder_resolver_backup(self):
        with self.archive(("./etc/resolv.conf", "./etc/.resolv.conf.systemd-resolved.bak")) as archive:
            with self.assertRaisesRegex(ValueError, "host resolver backup"):
                INPUT_LOCK.reject_host_resolver_backup(archive)

    def test_accepts_rootfs_without_builder_resolver_backup(self):
        with self.archive(("./etc/resolv.conf",)) as archive:
            INPUT_LOCK.reject_host_resolver_backup(archive)


if __name__ == "__main__":
    unittest.main()
