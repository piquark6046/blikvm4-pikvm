"""A/B candidate comparison checks actual compressed bytes and provenance."""

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "build/release"))
import compare  # noqa: E402


class ReleaseCompareTests(unittest.TestCase):
    def candidate(self, path: Path, raw: bytes) -> None:
        path.mkdir()
        image = path / "blikvm-v4-pikvm.img.zst"
        subprocess.run(["zstd", "-q", "-19", "-T1", "-o", str(image)],
                       input=raw, check=True, capture_output=True)
        (path / "filesystem-manifest.json").write_text("{}\n")
        (path / "image-inputs.lock.json").write_text("{}\n")
        (path / "bootloader-layout.json").write_text(json.dumps({
            "type": "source-built-candidate", "bootloader_extents": [{"sha256": "b" * 64}]}))
        (path / "package-inventory.tsv").write_text("package\t1\tarm64\n")
        source = {"git_commit": "c" * 40,
                  "bootloader": json.loads((path / "bootloader-layout.json").read_text()),
                  "package_inventory_sha256": compare.sha(path / "package-inventory.tsv"),
                  "tool_versions": {"mkimage": "test"}, "tool_binary_sha256": {"mkimage": "d" * 64},
                  "container_base_digests": {"assembly": "sha256:test"},
                  "ubuntu_snapshot": "20260906T000000Z",
                  "release_builder_inputs_sha256": {"AssemblyContainerfile": "e" * 64}}
        (path / "source-manifest.json").write_text(json.dumps(source))
        (path / "validation.json").write_text(json.dumps({
            "result": "passed", "secret_scan": {"result": "passed"}}))
        data = {"git_commit": "c" * 40, "public_image_sha256": compare.hashlib.sha256(raw).hexdigest(),
                "public_image_bytes": len(raw), "compressed_image_sha256": compare.sha(image),
                "filesystem_manifest_sha256": compare.sha(path / "filesystem-manifest.json"),
                "release_input_lock_sha256": compare.sha(path / "image-inputs.lock.json"),
                "source_manifest_sha256": compare.sha(path / "source-manifest.json"),
                "bootloader_sha256": "b" * 64, "offline_validation": "PASSED", "secret_scan": "PASSED",
                "runner_image": {"image_os": "ubuntu", "image_version": "test"}}
        (path / "manifest.json").write_text(json.dumps({
            "image_sha256": data["public_image_sha256"],
            "compressed_image_sha256": data["compressed_image_sha256"],
            "rootfs_inventory_sha256": data["filesystem_manifest_sha256"],
            "vendor_bootloader": source["bootloader"]}))
        (path / "candidate-manifest.json").write_text(json.dumps(data))

    def test_equal_candidates_generate_verified_assets(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.candidate(root / "a", b"public raw image bytes" * 100)
            self.candidate(root / "b", b"public raw image bytes" * 100)
            release = {"tag": "1.2.5-beta.2", "channel": "beta", "prerelease": True,
                       "git_commit": "c" * 40, "git_short_commit": "c" * 8}
            compare.compare(root / "a", root / "b", root / "dist", release)
            manifest = json.loads((root / "dist/release-manifest.json").read_text())
            self.assertEqual(manifest["qualification"]["p3"], "UNACCEPTED")
            self.assertEqual(manifest["qualification"]["core_kvm"], "NOT_CLAIMED")
            self.assertEqual(manifest["build_runner_images"]["a"]["image_version"], "test")
            self.assertNotIn(".img", {path.suffix for path in (root / "dist").iterdir()})
            for line in (root / "dist/SHA256SUMS").read_text().splitlines():
                digest, name = line.split("  ")
                self.assertEqual(digest, compare.sha(root / "dist" / name))

    def test_different_raw_bytes_fail_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.candidate(root / "a", b"A" * 100)
            self.candidate(root / "b", b"B" * 100)
            release = {"tag": "1.2.5-beta.2", "channel": "beta", "prerelease": True,
                       "git_commit": "c" * 40, "git_short_commit": "c" * 8}
            with self.assertRaisesRegex(ValueError, "builders disagree"):
                compare.compare(root / "a", root / "b", root / "dist", release)
            self.assertFalse((root / "dist").exists())


if __name__ == "__main__":
    unittest.main()
