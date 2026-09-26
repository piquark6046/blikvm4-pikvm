#!/usr/bin/env python3
"""Record and verify immutable artifacts within one clean release build."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import stat


REPO = Path(__file__).resolve().parents[2]
LOCK = REPO / "out/release/inputs.lock.json"


def key(path: Path) -> str:
    path = path.absolute()
    if not path.is_relative_to(REPO / "out") or not path.resolve().is_relative_to(REPO / "out"):
        raise ValueError("release input must be under out/")
    if not stat.S_ISREG(path.lstat().st_mode):
        raise ValueError("release input must be a regular file")
    return path.relative_to(REPO).as_posix()


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def load() -> dict:
    if LOCK.is_symlink():
        raise ValueError("release input lock must be a regular file")
    return json.loads(LOCK.read_text()) if LOCK.exists() else {"schema_version": 1, "inputs": {}}


def record(paths: list[Path]) -> None:
    data = load()
    for path in paths:
        name = key(path)
        item = {"sha256": digest(path), "size": path.stat().st_size}
        prior = data["inputs"].get(name)
        if prior is not None and prior != item:
            raise ValueError(f"recorded release input changed: {name}")
        data["inputs"][name] = item
    LOCK.parent.mkdir(parents=True, exist_ok=True)
    temporary = LOCK.with_suffix(".tmp")
    with temporary.open("x") as stream:
        json.dump(data, stream, indent=2, sort_keys=True)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(LOCK)


def verify(paths: list[Path]) -> None:
    data = load()["inputs"]
    for path in paths:
        name = key(path)
        item = data.get(name)
        if item is None or item != {"sha256": digest(path), "size": path.stat().st_size}:
            raise ValueError(f"unrecorded or changed release input: {name}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("record", "verify", "verify-list"))
    parser.add_argument("paths", nargs="+")
    args = parser.parse_args()
    if args.command == "verify-list":
        paths = []
        for name in args.paths:
            for line in Path(name).read_text().splitlines():
                fields = line.split(maxsplit=1)
                if len(fields) != 2:
                    raise ValueError("invalid historical checksum list")
                paths.append(REPO / fields[1].lstrip("*"))
        verify(paths)
    elif args.command == "record":
        record([Path(path) for path in args.paths])
    else:
        verify([Path(path) for path in args.paths])


if __name__ == "__main__":
    main()
