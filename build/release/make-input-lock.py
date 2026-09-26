#!/usr/bin/env python3
"""Bind a new public image to freshly built, independently checked inputs."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import stat
import tarfile


REPO = Path(__file__).resolve().parents[2]
HISTORICAL = json.loads((REPO / "build/image/inputs.lock.json").read_text())


def record(path: Path) -> dict:
    if not path.is_file() or path.is_symlink() or not path.resolve().is_relative_to(REPO / "out"):
        raise ValueError(f"invalid release input: {path}")
    with path.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    return {"path": path.relative_to(REPO).as_posix(), "size": path.stat().st_size, "sha256": digest}


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    mapping = {
        "Image": REPO / "out/kvmd-lan/artifacts/Image",
        "linux.config": REPO / "out/kvmd-lan/artifacts/linux.config",
        "sun50i-h616-blikvm-v4.dtb": REPO / "out/kvmd-lan/artifacts/sun50i-h616-blikvm-v4.dtb",
        "rootfs.tar.gz": REPO / "out/release/logging/rootfs.tar.gz",
        "initramfs.cpio.gz": REPO / "out/release/logging/initramfs.cpio.gz",
        "kvmd-web_4.213-1blikvm4_arm64.deb": REPO / "out/kvmd-msd/artifacts/kvmd-web_4.213-1blikvm4_arm64.deb",
        "ustreamer_6.65-1blikvm2_arm64.deb": REPO / "out/ustreamer/artifacts/ustreamer_6.65-1blikvm2_arm64.deb",
    }
    inputs = {name: record(path) for name, path in mapping.items()}
    contracts = HISTORICAL["contracts"]
    with tarfile.open(mapping["rootfs.tar.gz"]) as archive:
        for name, expected in contracts.items():
            member = archive.getmember("./" + name)
            if not member.isfile():
                raise ValueError(f"contract is not a file: {name}")
            payload = archive.extractfile(member).read()
            observed = {
                "sha256": hashlib.sha256(payload).hexdigest(),
                "size": member.size,
                "uid": member.uid,
                "gid": member.gid,
                "mode": stat.S_IMODE(member.mode),
            }
            if observed != expected:
                raise ValueError(f"accepted product contract changed: {name}")
    data = {
        "schema_version": 1,
        "inputs": inputs,
        "contracts": contracts,
        "linux_patch_sha256": HISTORICAL["linux_patch_sha256"],
        "source_date_epoch": HISTORICAL["source_date_epoch"],
        "historical_contract_tag": HISTORICAL["acceptance_tag"],
        "release_input_source": "fresh clean build",
    }
    output = args.output.resolve()
    if not output.is_relative_to(REPO / "out/release"):
        raise ValueError("lock output must be under out/release")
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x") as stream:
        json.dump(data, stream, indent=2, sort_keys=True)
        stream.write("\n")


if __name__ == "__main__":
    main()
