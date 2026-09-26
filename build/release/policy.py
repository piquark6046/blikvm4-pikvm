#!/usr/bin/env python3
"""Fail-closed policy for exact-byte GitHub Release publication."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import stat


REPO = Path(__file__).resolve().parents[2]


class ReleaseBlocked(ValueError):
    pass


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def verify_checksums(dist: Path) -> None:
    if dist.is_symlink() or not dist.is_dir():
        raise ReleaseBlocked("PUBLIC_ASSET_DIRECTORY_INVALID")
    for path in dist.iterdir():
        if path.is_symlink() or not stat.S_ISREG(path.lstat().st_mode):
            raise ReleaseBlocked("PUBLIC_ASSET_TYPE_INVALID")
    lines = (dist / "SHA256SUMS").read_text().splitlines()
    names = set()
    for line in lines:
        match = re.fullmatch(r"([0-9a-f]{64})  ([A-Za-z0-9._-]+)", line)
        if not match:
            raise ReleaseBlocked("CHECKSUM_MANIFEST_INVALID")
        expected, name = match.groups()
        if name in names or name == "SHA256SUMS" or digest(dist / name) != expected:
            raise ReleaseBlocked("CHECKSUM_MISMATCH")
        names.add(name)
    actual = {p.name for p in dist.iterdir() if p.is_file() and p.name != "SHA256SUMS"}
    if names != actual:
        raise ReleaseBlocked("CHECKSUM_MANIFEST_INCOMPLETE")


def evidence_matches(item: dict) -> bool:
    relative = item.get("evidence")
    expected = item.get("evidence_sha256")
    if not isinstance(relative, str) or not isinstance(expected, str) or not re.fullmatch(r"[0-9a-f]{64}", expected):
        return False
    target = (REPO / relative).resolve()
    return (target.is_relative_to(REPO / "research/evidence") and target.is_file()
            and digest(target) == expected)


def qualification_status(manifest: dict, record: dict) -> dict:
    if record.get("schema_version") != 1:
        raise ReleaseBlocked("QUALIFICATION_RECORD_INVALID")
    if (record.get("p3"), record.get("m6_atx"), record.get("ro_overlay")) != (
            "UNACCEPTED", "DEFERRED", "DEFERRED"):
        raise ReleaseBlocked("UNQUALIFIED_SCOPE_CLAIM")
    image = manifest["public_image"]["sha256"]
    boot = manifest["bootloader_sha256"]
    qualified_boot = next((x for x in record["qualified_bootloaders"]
                           if x["sha256"] == boot and x.get("result") == "PASSED"
                           and evidence_matches(x)), None)
    matched = next((x for x in record["qualified_public_images"]
                    if x["sha256"] == image and x.get("core_kvm") == "PASSED"
                    and x.get("p2") == "PASSED" and x.get("bootloader_sha256") == boot
                    and evidence_matches(x)), None) if qualified_boot else None
    return {
        "bootloader_hardware": "PASSED" if qualified_boot else "NOT_CLAIMED",
        "bootloader_evidence": qualified_boot["evidence"] if qualified_boot else None,
        "core_kvm": "PASSED" if matched else "NOT_CLAIMED",
        "p2": "PASSED" if matched else "NOT_CLAIMED",
        "p3": record["p3"], "m6_atx": record["m6_atx"],
        "ro_overlay": record["ro_overlay"],
        "evidence": matched["evidence"] if matched else None,
    }


def qualification(manifest: dict, record: dict) -> dict:
    status = qualification_status(manifest, record)
    if status["bootloader_hardware"] != "PASSED":
        raise ReleaseBlocked("BOOTLOADER_HARDWARE_QUALIFICATION_BLOCKED")
    if manifest["channel"] == "stable" and status["core_kvm"] != "PASSED":
        raise ReleaseBlocked("STABLE_EXACT_IMAGE_NOT_QUALIFIED")
    return status


def prepublish(dist: Path, record_path: Path | None = None) -> dict:
    dist = dist.resolve()
    verify_checksums(dist)
    manifest = json.loads((dist / "release-manifest.json").read_text())
    if manifest.get("channel") == "build":
        raise ReleaseBlocked("BUILD_TAG_CANDIDATE_ONLY")
    tag = manifest["release_tag"]
    image_name = f"blikvm-v4-pikvm-{tag}.img.zst"
    allowed = {image_name, "filesystem-manifest.json", "image-inputs.lock.json",
               "source-manifest.json", "bootloader-layout.json", "package-inventory.tsv",
               "ENROLLMENT.md", "FLASHING.md", "THIRD_PARTY_NOTICES.md",
               "blikvm-enroll.tar.gz", "release-manifest.json", "SHA256SUMS"}
    if {p.name for p in dist.iterdir()} != allowed:
        raise ReleaseBlocked("PUBLIC_ASSET_ALLOWLIST_FAILED")
    if manifest["compressed_image"]["name"] != image_name or digest(dist / image_name) != manifest["compressed_image"]["sha256"]:
        raise ReleaseBlocked("COMPRESSED_IMAGE_HASH_MISMATCH")
    if (digest(dist / "filesystem-manifest.json") != manifest["filesystem_manifest_sha256"]
            or digest(dist / "image-inputs.lock.json") != manifest["release_input_lock_sha256"]):
        raise ReleaseBlocked("RELEASE_MANIFEST_HASH_MISMATCH")
    source = json.loads((dist / "source-manifest.json").read_text())
    layout = json.loads((dist / "bootloader-layout.json").read_text())
    if (source.get("git_commit") != manifest["git_commit"]
            or source.get("inputs_lock_sha256") != digest(dist / "image-inputs.lock.json")
            or source.get("package_inventory_sha256") != digest(dist / "package-inventory.tsv")
            or source.get("bootloader") != layout):
        raise ReleaseBlocked("SOURCE_MANIFEST_MISMATCH")
    expected_inputs = {"release_input_lock_sha256": digest(dist / "image-inputs.lock.json"),
                       "source_manifest_sha256": digest(dist / "source-manifest.json"),
                       "package_inventory_sha256": digest(dist / "package-inventory.tsv"),
                       "bootloader_layout_sha256": digest(dist / "bootloader-layout.json")}
    expected_toolchain = {name: source[name] for name in
                          ("tool_versions", "tool_binary_sha256", "container_base_digests",
                           "ubuntu_snapshot", "release_builder_inputs_sha256")}
    if manifest.get("inputs") != expected_inputs or manifest.get("toolchain") != expected_toolchain:
        raise ReleaseBlocked("RELEASE_PROVENANCE_MISMATCH")
    if source["bootloader"]["type"] != "source-built-candidate":
        raise ReleaseBlocked("BOOTLOADER_REDISTRIBUTION_BLOCKED")
    if source["bootloader"]["bootloader_extents"][0]["sha256"] != manifest["bootloader_sha256"]:
        raise ReleaseBlocked("BOOTLOADER_PROVENANCE_MISMATCH")
    if manifest.get("reproducible_build") is not True or manifest.get("build_jobs") != 2:
        raise ReleaseBlocked("REPRODUCIBILITY_NOT_PROVEN")
    if manifest.get("offline_validation") != "PASSED" or manifest.get("secret_scan") != "PASSED":
        raise ReleaseBlocked("PUBLIC_IMAGE_VALIDATION_FAILED")
    license_path = REPO / "LICENSE"
    license_text = license_path.read_text() if license_path.is_file() else ""
    if not license_text.strip() or any(marker in license_text.upper()
                                       for marker in ("TODO", "INCOMPLETE")):
        raise ReleaseBlocked("PROJECT_LICENSE_BLOCKED")
    if source.get("project_license_sha256") != digest(license_path):
        raise ReleaseBlocked("PROJECT_LICENSE_PROVENANCE_MISMATCH")
    notices = (dist / "THIRD_PARTY_NOTICES.md").read_text()
    if not notices.strip() or "INCOMPLETE" in notices.upper() or "TODO" in notices.upper():
        raise ReleaseBlocked("THIRD_PARTY_NOTICES_BLOCKED")
    record = json.loads((record_path or REPO / "release/qualification.json").read_text())
    status = qualification(manifest, record)
    if manifest["qualification"] != status:
        raise ReleaseBlocked("QUALIFICATION_MANIFEST_MISMATCH")
    return manifest
