"""Publication gates for exact image qualification and immutable assets."""

import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "build/release"))
import policy  # noqa: E402


class ReleasePolicyTests(unittest.TestCase):
    def fixture(self, root: Path, channel: str = "stable") -> tuple[Path, dict]:
        dist = root / "dist"
        dist.mkdir()
        tag = "1.2.5-build.cccccccc" if channel == "build" else "1.2.5"
        image_name = f"blikvm-v4-pikvm-{tag}.img.zst"
        other = ("filesystem-manifest.json", "image-inputs.lock.json",
                 "bootloader-layout.json", "package-inventory.tsv", "ENROLLMENT.md",
                 "FLASHING.md", "THIRD_PARTY_NOTICES.md", "package-notices.tsv",
                 "blikvm-enroll.tar.gz")
        for name in (image_name, *other):
            (dist / name).write_bytes(b"public")
        (dist / "THIRD_PARTY_NOTICES.md").write_text("reviewed notice inventory\n")
        (dist / "package-inventory.tsv").write_text("example\t1\tarm64\n")
        (dist / "package-notices.tsv").write_text(
            "package\tversion\tarchitecture\tdpkg_status\tsource\tlicense_document\tlicense_sha256\tlicense_terms\n"
            "example\t1\tarm64\tinstall ok installed\texample\t/usr/share/doc/example/copyright\t"
            + "e" * 64 + "\tGPL-2+\n")
        boot = "b" * 64
        image = "a" * 64
        (root / "LICENSE").write_text("owner-selected license")
        bootloader = {"type": "source-built-candidate", "bootloader_extents": [{"sha256": boot}]}
        (dist / "bootloader-layout.json").write_text(json.dumps(bootloader))
        source = {
            "bootloader": bootloader, "git_commit": "c" * 40,
            "inputs_lock_sha256": policy.digest(dist / "image-inputs.lock.json"),
            "package_inventory_sha256": policy.digest(dist / "package-inventory.tsv"),
            "package_notices_sha256": policy.digest(dist / "package-notices.tsv"),
            "third_party_notices_sha256": policy.digest(dist / "THIRD_PARTY_NOTICES.md"),
            "project_license_sha256": policy.digest(root / "LICENSE"),
            "tool_versions": {"mkimage": "test"},
            "tool_binary_sha256": {"mkimage": "d" * 64},
            "container_base_digests": {"assembly": "sha256:test"},
            "ubuntu_snapshot": "20260906T000000Z",
            "release_builder_inputs_sha256": {"AssemblyContainerfile": "e" * 64}}
        (dist / "source-manifest.json").write_text(json.dumps(source))
        evidence = root / "research/evidence"
        evidence.mkdir(parents=True)
        (evidence / "boot.json").write_text("{}")
        (evidence / "image.json").write_text("{}")
        record = {"schema_version": 1,
                  "qualified_bootloaders": [{"sha256": boot, "result": "PASSED",
                    "evidence": "research/evidence/boot.json",
                    "evidence_sha256": policy.digest(evidence / "boot.json")}],
                  "qualified_public_images": [{"sha256": image, "core_kvm": "PASSED",
                    "p2": "PASSED", "bootloader_sha256": boot,
                    "evidence": "research/evidence/image.json",
                    "evidence_sha256": policy.digest(evidence / "image.json")}],
                  "p3": "UNACCEPTED", "m6_atx": "DEFERRED", "ro_overlay": "DEFERRED"}
        qpath = root / "qualification.json"
        qpath.write_text(json.dumps(record))
        manifest = {"release_tag": tag, "channel": channel, "git_commit": "c" * 40,
                    "filesystem_manifest_sha256": policy.digest(dist / "filesystem-manifest.json"),
                    "release_input_lock_sha256": policy.digest(dist / "image-inputs.lock.json"),
                    "inputs": {"release_input_lock_sha256": policy.digest(dist / "image-inputs.lock.json"),
                               "source_manifest_sha256": policy.digest(dist / "source-manifest.json"),
                               "package_inventory_sha256": policy.digest(dist / "package-inventory.tsv"),
                               "package_notices_sha256": policy.digest(dist / "package-notices.tsv"),
                               "third_party_notices_sha256": policy.digest(dist / "THIRD_PARTY_NOTICES.md"),
                               "bootloader_layout_sha256": policy.digest(dist / "bootloader-layout.json")},
                    "toolchain": {name: source[name] for name in
                                  ("tool_versions", "tool_binary_sha256", "container_base_digests",
                                   "ubuntu_snapshot", "release_builder_inputs_sha256")},
                    "compressed_image": {"name": image_name,
                                         "sha256": policy.digest(dist / image_name)},
                    "public_image": {"sha256": image}, "bootloader_sha256": boot,
                    "build_jobs": 2, "reproducible_build": True,
                    "offline_validation": "PASSED", "secret_scan": "PASSED",
                    "qualification": policy.qualification_status({"public_image": {"sha256": image},
                        "bootloader_sha256": boot}, record)}
        (dist / "release-manifest.json").write_text(json.dumps(manifest))
        (dist / "SHA256SUMS").write_text("".join(
            f"{policy.digest(path)}  {path.name}\n" for path in sorted(dist.iterdir()) if path.is_file()))
        return dist, record

    def test_stable_requires_exact_image_and_bootloader_evidence(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(policy, "REPO", Path(temp)):
            root = Path(temp)
            dist, record = self.fixture(root)
            qpath = root / "qualification.json"
            self.assertEqual(policy.prepublish(dist, qpath)["channel"], "stable")
            record["qualified_public_images"] = []
            qpath.write_text(json.dumps(record))
            with self.assertRaisesRegex(policy.ReleaseBlocked, "STABLE_EXACT_IMAGE_NOT_QUALIFIED"):
                policy.prepublish(dist, qpath)

    def test_build_tag_cannot_publish_even_with_qualification(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(policy, "REPO", Path(temp)):
            root = Path(temp)
            dist, _ = self.fixture(root, "build")
            with self.assertRaisesRegex(policy.ReleaseBlocked, "BUILD_TAG_CANDIDATE_ONLY"):
                policy.prepublish(dist, root / "qualification.json")

    def test_prerelease_still_requires_qualified_bootloader_and_license(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(policy, "REPO", Path(temp)):
            root = Path(temp)
            dist, record = self.fixture(root, "beta")
            qpath = root / "qualification.json"
            record["qualified_public_images"] = []
            qpath.write_text(json.dumps(record))
            manifest_path = dist / "release-manifest.json"
            manifest = json.loads(manifest_path.read_text())
            manifest["qualification"] = policy.qualification_status(manifest, record)
            manifest_path.write_text(json.dumps(manifest))
            (dist / "SHA256SUMS").write_text("".join(
                f"{policy.digest(path)}  {path.name}\n" for path in sorted(dist.iterdir())
                if path.is_file() and path.name != "SHA256SUMS"))
            self.assertEqual(policy.prepublish(dist, qpath)["qualification"]["core_kvm"],
                             "NOT_CLAIMED")
            record["qualified_bootloaders"] = []
            qpath.write_text(json.dumps(record))
            with self.assertRaisesRegex(policy.ReleaseBlocked, "BOOTLOADER_HARDWARE_QUALIFICATION_BLOCKED"):
                policy.prepublish(dist, qpath)
            (root / "LICENSE").unlink()
            with self.assertRaisesRegex(policy.ReleaseBlocked, "PROJECT_LICENSE_BLOCKED"):
                policy.prepublish(dist, qpath)

    def test_changed_asset_fails_checksum_gate(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(policy, "REPO", Path(temp)):
            dist, _ = self.fixture(Path(temp))
            (dist / "ENROLLMENT.md").write_bytes(b"modified")
            with self.assertRaisesRegex(policy.ReleaseBlocked, "CHECKSUM_MISMATCH"):
                policy.prepublish(dist, Path(temp) / "qualification.json")

    def test_rehashed_notice_change_still_fails_source_provenance(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(policy, "REPO", Path(temp)):
            dist, _ = self.fixture(Path(temp))
            notice = dist / "package-notices.tsv"
            notice.write_text(notice.read_text().replace("GPL-2+", "MIT"))
            (dist / "SHA256SUMS").write_text("".join(
                f"{policy.digest(path)}  {path.name}\n" for path in sorted(dist.iterdir())
                if path.is_file() and path.name != "SHA256SUMS"))
            with self.assertRaisesRegex(policy.ReleaseBlocked, "SOURCE_MANIFEST_MISMATCH"):
                policy.prepublish(dist, Path(temp) / "qualification.json")

    def test_deferred_scope_cannot_be_promoted_by_metadata_alone(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(policy, "REPO", Path(temp)):
            _, record = self.fixture(Path(temp))
            record["p3"] = "PASSED"
            with self.assertRaisesRegex(policy.ReleaseBlocked, "UNQUALIFIED_SCOPE_CLAIM"):
                policy.qualification_status({"public_image": {"sha256": "a" * 64},
                                             "bootloader_sha256": "b" * 64}, record)


if __name__ == "__main__":
    unittest.main()
