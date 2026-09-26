#!/usr/bin/env python3
"""Recheck the immutable tag and all local public assets before publication."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess

import policy
import version


def remote_objects(tag: str) -> tuple[str, str]:
    ref = f"refs/tags/{tag}"
    lines = subprocess.check_output(["git", "ls-remote", "--tags", "origin", ref, ref + "^{}"], text=True).splitlines()
    values = dict(line.split("\t", 1)[::-1] for line in lines)
    direct = values.get(ref, "")
    return direct, values.get(ref + "^{}", direct)


def check(dist: Path, tag: str, ref: str) -> dict:
    classified = version.classify_ref(tag, ref)
    manifest = policy.prepublish(dist)
    if any(manifest[name] != classified[name] for name in
           ("release_tag", "channel", "prerelease", "git_commit", "git_short_commit", "tag_object")
           if name != "release_tag") or manifest["release_tag"] != classified["tag"]:
        raise policy.ReleaseBlocked("TAG_MANIFEST_MISMATCH")
    if remote_objects(tag) != (classified["tag_object"], classified["git_commit"]):
        raise policy.ReleaseBlocked("TAG_MOVED_OR_MISSING")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dist", type=Path, required=True)
    parser.add_argument("--tag", required=True)
    parser.add_argument("--ref", required=True)
    args = parser.parse_args()
    try:
        result = check(args.dist, args.tag, args.ref)
    except (policy.ReleaseBlocked, version.InvalidTag) as exc:
        print(json.dumps({"result": "blocked", "reason": str(exc)}))
        raise SystemExit(1) from exc
    print(json.dumps({"result": "passed", "release_tag": result["release_tag"]}))


if __name__ == "__main__":
    main()
