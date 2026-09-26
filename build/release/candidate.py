#!/usr/bin/env python3
"""Package only public, offline-validated output from one clean builder."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys


REPO = Path(__file__).resolve().parents[2]


def env_file(path: Path) -> dict[str, str]:
    return dict(line.split("=", 1) for line in path.read_text().splitlines()
                if line and not line.startswith("#") and "=" in line)


def sha(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main(source: Path, target: Path) -> None:
    source = source.resolve()
    target = target.resolve()
    if not source.is_relative_to(REPO / "out/release") or not target.is_relative_to(REPO / "out/release"):
        raise ValueError("candidate paths must be under out/release")
    manifest = json.loads((source / "manifest.json").read_text())
    validation = json.loads((source / "validation.json").read_text())
    if validation["result"] != "passed" or validation["secret_scan"]["result"] != "passed":
        raise ValueError("offline image validation or secret scan failed")
    image = source / "blikvm-v4-pikvm.img"
    compressed = source / "blikvm-v4-pikvm.img.zst"
    if sha(image) != manifest["image_sha256"] or sha(compressed) != manifest["compressed_image_sha256"]:
        raise ValueError("assembled image hash changed")
    target.mkdir(exist_ok=False)
    for name in ("blikvm-v4-pikvm.img.zst", "filesystem-manifest.json", "validation.json",
                 "bootloader-layout.json", "manifest.json"):
        shutil.copyfile(source / name, target / name)
    lock = REPO / "out/release/image-inputs.lock.json"
    shutil.copyfile(lock, target / "image-inputs.lock.json")
    shutil.copyfile(REPO / "out/kvmd-msd/artifacts/packages.tsv", target / "package-inventory.tsv")
    layout = REPO / "out/release/bootloader/layout.json"
    boot = json.loads(layout.read_text())
    if boot.get("type") != "source-built-candidate" or len(boot.get("bootloader_extents", [])) != 1:
        raise ValueError("unexpected bootloader provenance")
    linux = env_file(REPO / "build/versions.env")
    ubuntu = env_file(REPO / "build/ubuntu/versions.env")
    ustreamer = env_file(REPO / "build/ustreamer/versions.env")
    kvmd = env_file(REPO / "build/kvmd/versions.env")
    source_manifest = {
        "schema_version": 1,
        "git_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "inputs_lock_sha256": sha(lock),
        "bootloader": boot,
        "tool_versions": manifest["tool_versions"],
        "tool_binary_sha256": manifest["tool_binary_sha256"],
        "ubuntu_snapshot": manifest["ubuntu"]["snapshot"],
        "package_inventory_sha256": sha(target / "package-inventory.tsv"),
        "project_license_sha256": sha(REPO / "LICENSE") if (REPO / "LICENSE").is_file() else None,
        "public_upstream_inputs": {
            "linux": {"url": f"https://cdn.kernel.org/pub/linux/kernel/v7.x/linux-{linux['LINUX_VERSION']}.tar.xz",
                      "sha256": linux["LINUX_SHA256"]},
            "ubuntu_base": {"url": ubuntu["UBUNTU_URL"] + "/" + ubuntu["UBUNTU_ARCHIVE"],
                            "sha256": ubuntu["UBUNTU_SHA256"]},
            "ustreamer": {"url": ustreamer["USTREAMER_URL"], "sha256": ustreamer["USTREAMER_SHA256"]},
            "kvmd": {"url": kvmd["KVMD_URL"], "sha256": kvmd["KVMD_SHA256"]},
            "u_boot": {"url": "https://github.com/u-boot/u-boot.git", "commit": boot["u_boot_commit"]},
            "tf_a": {"url": "https://github.com/ARM-software/arm-trusted-firmware.git",
                     "commit": boot["tf_a_commit"]},
        },
        "container_base_digests": {"linux": linux["TOOLCHAIN_BASE"],
                                   "ubuntu": ubuntu["BUILDER_BASE"],
                                   "bootloader": linux["TOOLCHAIN_BASE"],
                                   "assembly": linux["TOOLCHAIN_BASE"]},
        "release_builder_inputs_sha256": {
            name: sha(REPO / "build/release" / name) for name in
            ("BootloaderContainerfile", "KernelContainerfile", "AssemblyContainerfile",
             "kernel-requirements.txt", "kernel-build-requirements.txt")},
    }
    (target / "source-manifest.json").write_text(json.dumps(source_manifest, indent=2, sort_keys=True) + "\n")
    candidate = {
        "schema_version": 1,
        "git_commit": source_manifest["git_commit"],
        "public_image_sha256": manifest["image_sha256"],
        "public_image_bytes": image.stat().st_size,
        "compressed_image_sha256": sha(target / "blikvm-v4-pikvm.img.zst"),
        "filesystem_manifest_sha256": sha(target / "filesystem-manifest.json"),
        "release_input_lock_sha256": sha(target / "image-inputs.lock.json"),
        "source_manifest_sha256": sha(target / "source-manifest.json"),
        "bootloader_sha256": boot["bootloader_extents"][0]["sha256"],
        "offline_validation": "PASSED",
        "secret_scan": "PASSED",
        "hardware_qualification": "NOT_CLAIMED",
        "runner_image": {"image_os": os.environ.get("ImageOS"),
                         "image_version": os.environ.get("ImageVersion"),
                         "runner_os": os.environ.get("RUNNER_OS"),
                         "runner_arch": os.environ.get("RUNNER_ARCH")},
    }
    (target / "candidate-manifest.json").write_text(json.dumps(candidate, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("usage: candidate.py <assembly> <new-candidate-directory>")
    main(Path(sys.argv[1]), Path(sys.argv[2]))
