#!/usr/bin/env python3
"""Compare two clean builders and prepare deterministic public release assets."""

from __future__ import annotations

import argparse
import filecmp
import gzip
import hashlib
import io
import json
from pathlib import Path
import shutil
import stat
import subprocess
import tarfile

import version
import policy


REPO = Path(__file__).resolve().parents[2]
EPOCH = 1788652800
EQUAL = ("public_image_sha256", "public_image_bytes", "compressed_image_sha256",
         "filesystem_manifest_sha256", "release_input_lock_sha256", "source_manifest_sha256",
         "bootloader_sha256", "git_commit", "offline_validation", "secret_scan")


def sha(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read_candidate(path: Path) -> dict:
    expected_files = {"blikvm-v4-pikvm.img.zst", "filesystem-manifest.json",
                      "validation.json", "bootloader-layout.json", "manifest.json",
                      "image-inputs.lock.json", "package-inventory.tsv",
                      "source-manifest.json", "candidate-manifest.json"}
    if ({item.name for item in path.iterdir()} != expected_files
            or any(item.is_symlink() or not stat.S_ISREG(item.lstat().st_mode)
                   for item in path.iterdir())):
        raise ValueError("candidate contains unexpected asset or file type")
    data = json.loads((path / "candidate-manifest.json").read_text())
    expected = {
        "compressed_image_sha256": "blikvm-v4-pikvm.img.zst",
        "filesystem_manifest_sha256": "filesystem-manifest.json",
        "release_input_lock_sha256": "image-inputs.lock.json",
        "source_manifest_sha256": "source-manifest.json",
    }
    for field, name in expected.items():
        if sha(path / name) != data[field]:
            raise ValueError(f"candidate {field} mismatch")
    validation = json.loads((path / "validation.json").read_text())
    if validation["result"] != "passed" or validation["secret_scan"]["result"] != "passed":
        raise ValueError("candidate validation failed")
    if data["offline_validation"] != "PASSED" or data["secret_scan"] != "PASSED":
        raise ValueError("candidate status mismatch")
    source = json.loads((path / "source-manifest.json").read_text())
    layout = json.loads((path / "bootloader-layout.json").read_text())
    if source["bootloader"] != layout or source["package_inventory_sha256"] != sha(path / "package-inventory.tsv"):
        raise ValueError("candidate provenance files disagree")
    if source["git_commit"] != data["git_commit"] or layout["bootloader_extents"][0]["sha256"] != data["bootloader_sha256"]:
        raise ValueError("candidate source or bootloader hash mismatch")
    assembled = json.loads((path / "manifest.json").read_text())
    if (assembled["image_sha256"] != data["public_image_sha256"]
            or assembled["compressed_image_sha256"] != data["compressed_image_sha256"]
            or assembled["rootfs_inventory_sha256"] != data["filesystem_manifest_sha256"]
            or assembled["vendor_bootloader"] != layout):
        raise ValueError("candidate assembly manifest disagrees")
    return data


def enrollment_bundle(target: Path) -> None:
    files = {
        "enroll.py": REPO / "build/release/enroll.py",
        "assemble.py": REPO / "build/image/assemble.py",
        "boot.cmd": REPO / "build/image/boot.cmd",
        "mke2fs.conf": REPO / "build/image/mke2fs.conf",
        "public-constants.json": REPO / "build/image/public-constants.json",
    }
    with target.open("xb") as output:
        with gzip.GzipFile(filename="", fileobj=output, mode="wb", mtime=0, compresslevel=9) as compressed:
            with tarfile.open(fileobj=compressed, mode="w|", format=tarfile.GNU_FORMAT) as archive:
                for name, source in sorted(files.items()):
                    payload = source.read_bytes()
                    info = tarfile.TarInfo(name)
                    info.size = len(payload)
                    info.mode = 0o755 if name == "enroll.py" else 0o644
                    info.uid = info.gid = 0
                    info.mtime = EPOCH
                    archive.addfile(info, io.BytesIO(payload))


def compare(first: Path, second: Path, dist: Path, release: dict) -> None:
    a, b = read_candidate(first), read_candidate(second)
    if any(a[field] != b[field] for field in EQUAL):
        raise ValueError("independent release builders disagree")
    if not filecmp.cmp(first / "blikvm-v4-pikvm.img.zst", second / "blikvm-v4-pikvm.img.zst", shallow=False):
        raise ValueError("compressed image bytes disagree")
    decoded = subprocess.Popen(["zstd", "-q", "-d", "-c", str(first / "blikvm-v4-pikvm.img.zst")],
                               stdout=subprocess.PIPE)
    with decoded.stdout:
        raw_digest = hashlib.file_digest(decoded.stdout, "sha256").hexdigest()
    if decoded.wait() != 0 or raw_digest != a["public_image_sha256"]:
        raise ValueError("compressed image does not decode to the claimed raw image")
    for name in ("filesystem-manifest.json", "image-inputs.lock.json", "source-manifest.json",
                 "bootloader-layout.json", "package-inventory.tsv"):
        if not filecmp.cmp(first / name, second / name, shallow=False):
            raise ValueError(f"independent builders disagree: {name}")
    if a["git_commit"] != release["git_commit"]:
        raise ValueError("built source differs from classified tag")
    dist.mkdir(exist_ok=False)
    image_name = f"blikvm-v4-pikvm-{release['tag']}.img.zst"
    shutil.copyfile(first / "blikvm-v4-pikvm.img.zst", dist / image_name)
    for name in ("filesystem-manifest.json", "image-inputs.lock.json", "source-manifest.json",
                 "bootloader-layout.json", "package-inventory.tsv"):
        shutil.copyfile(first / name, dist / name)
    for source, target in (("ENROLLMENT.md", "ENROLLMENT.md"),
                           ("FLASHING.md", "FLASHING.md"),
                           ("THIRD_PARTY_NOTICES.md", "THIRD_PARTY_NOTICES.md")):
        shutil.copyfile(REPO / "release" / source, dist / target)
    enrollment_bundle(dist / "blikvm-enroll.tar.gz")
    record = json.loads((REPO / "release/qualification.json").read_text())
    source_manifest = json.loads((dist / "source-manifest.json").read_text())
    status = policy.qualification_status({"public_image": {"sha256": a["public_image_sha256"]},
                                          "bootloader_sha256": a["bootloader_sha256"]}, record)
    artifacts = {p.name: {"sha256": sha(p), "size": p.stat().st_size}
                 for p in sorted(dist.iterdir()) if p.is_file()}
    manifest = {
        "schema_version": 1, "project": "blikvm4-pikvm", "board": "BliKVM v4",
        "release_tag": release["tag"], "channel": release["channel"],
        "prerelease": release["prerelease"], "git_commit": release["git_commit"],
        "git_short_commit": release["git_short_commit"],
        "tag_object": release.get("tag_object"),
        "source_date_epoch": EPOCH, "github_runner_label": "ubuntu-26.04",
        "build_runner_images": {"a": a.get("runner_image"), "b": b.get("runner_image")},
        "build_jobs": 2, "reproducible_build": True,
        "offline_validation": "PASSED", "secret_scan": "PASSED",
        "public_image": {"uncompressed_bytes": a["public_image_bytes"], "sha256": a["public_image_sha256"]},
        "compressed_image": {"name": image_name, "sha256": a["compressed_image_sha256"]},
        "filesystem_manifest_sha256": a["filesystem_manifest_sha256"],
        "release_input_lock_sha256": a["release_input_lock_sha256"],
        "bootloader_sha256": a["bootloader_sha256"],
        "inputs": {"release_input_lock_sha256": a["release_input_lock_sha256"],
                   "source_manifest_sha256": a["source_manifest_sha256"],
                   "package_inventory_sha256": sha(dist / "package-inventory.tsv"),
                   "bootloader_layout_sha256": sha(dist / "bootloader-layout.json")},
        "toolchain": {"tool_versions": source_manifest["tool_versions"],
                      "tool_binary_sha256": source_manifest["tool_binary_sha256"],
                      "container_base_digests": source_manifest["container_base_digests"],
                      "ubuntu_snapshot": source_manifest["ubuntu_snapshot"],
                      "release_builder_inputs_sha256": source_manifest["release_builder_inputs_sha256"]},
        "qualification": status, "artifacts": artifacts,
    }
    (dist / "release-manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    (dist / "SHA256SUMS").write_text("".join(
        f"{sha(path)}  {path.name}\n" for path in sorted(dist.iterdir()) if path.is_file()))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("first", type=Path)
    parser.add_argument("second", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--tag", required=True)
    parser.add_argument("--ref")
    parser.add_argument("--commit")
    parser.add_argument("--tag-object", help="tag object ID captured before both builds")
    args = parser.parse_args()
    if args.ref:
        release = version.classify_ref(args.tag, args.ref)
        if release["tag_object"] != args.tag_object:
            raise ValueError("release tag moved since build classification")
    elif args.commit:
        if args.tag_object:
            parser.error("--tag-object is only valid with --ref")
        release = version.classify(args.tag, version.resolve_commit(args.commit), version.short_commit(args.commit))
    else:
        parser.error("--ref or --commit required")
    compare(args.first, args.second, args.output, release)


if __name__ == "__main__":
    main()
