#!/usr/bin/env python3
"""Write a machine-readable manifest for the current serial-boot artifacts."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]


def read_versions() -> dict[str, str]:
    values: dict[str, str] = {}
    for line in (ROOT / "build" / "versions.env").read_text().splitlines():
        if line and not line.startswith("#"):
            key, value = line.split("=", 1)
            values[key] = value
    return values


def file_record(path: Path) -> dict[str, object]:
    return {
        "name": path.name,
        "size": path.stat().st_size,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def main() -> None:
    versions = read_versions()
    artifact_root = ROOT / "out" / "build" / "artifacts"
    names = (
        "Image",
        "sun50i-h616-blikvm-v4.dtb",
        "initramfs.cpio.gz",
        "linux.config",
    )
    manifest = {
        "schema_version": 1,
        "linux": {
            "version": versions["LINUX_VERSION"],
            "source_sha256": versions["LINUX_SHA256"],
        },
        "initramfs": {
            "distribution": "Alpine Linux",
            "version": versions["ALPINE_VERSION"],
            "source_sha256": versions["ALPINE_SHA256"],
            "init": "/init",
            "ready_marker": "BLIKVM_INITRAMFS_READY",
            "network_utilities": ["ip", "ping"],
            "usb_inspection_utilities": ["lsusb", "lsusb -t"],
        },
        "build": {
            "default_jobs": 3,
            "toolchain_image": versions["TOOLCHAIN_IMAGE"],
            "toolchain_image_id": sys.argv[1],
            "toolchain_base": versions["TOOLCHAIN_BASE"],
            "incremental_output": f"out/build/linux-{versions['LINUX_VERSION']}",
        },
        "artifacts": {name: file_record(artifact_root / name) for name in names},
    }
    (artifact_root / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
