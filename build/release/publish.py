#!/usr/bin/env python3
"""Publish verified assets without replacing conflicting existing bytes."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile

import policy
import prepublish


def gh(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(["gh", *args], check=check, capture_output=True, text=True)


def notes(manifest: dict) -> str:
    q = manifest["qualification"]
    return (
        f"BliKVM v4 PiKVM {manifest['release_tag']}\n\n"
        f"Channel: {manifest['channel']}\nGit commit: {manifest['git_commit']}\n"
        f"Public raw image SHA-256: {manifest['public_image']['sha256']}\n"
        f"Compressed image SHA-256: {manifest['compressed_image']['sha256']}\n"
        "Independent clean builds: 2, byte-identical image and compression.\n"
        f"Hardware qualification: bootloader {q['bootloader_hardware']}; core KVM {q['core_kvm']}; P2 {q['p2']}.\n"
        f"P3 {q['p3']}; ATX {q['m6_atx']}; RO/overlay {q['ro_overlay']}.\n"
        "Offline user enrollment is required before use. See ENROLLMENT.md and FLASHING.md.\n"
        + (f"Build suffix is the tagged source commit's eight-character Git ID.\n"
           if manifest["channel"] == "build" else "")
    )


def publish(dist: Path, tag: str, ref: str) -> None:
    if not os.environ.get("GH_TOKEN") and not os.environ.get("GITHUB_TOKEN"):
        raise policy.ReleaseBlocked("GITHUB_TOKEN_MISSING")
    manifest = prepublish.check(dist, tag, ref)
    fields = "assets,body,isDraft,isPrerelease,name,tagName,targetCommitish"
    view = gh("release", "view", tag, "--json", fields, check=False)
    created = False
    with tempfile.TemporaryDirectory(prefix="blikvm-release-") as temp:
        private = Path(temp)
        note = private / "notes.txt"
        note.write_text(notes(manifest))
        if view.returncode:
            if "release not found" not in view.stderr.lower() and "http 404" not in view.stderr.lower():
                raise policy.ReleaseBlocked("GITHUB_RELEASE_LOOKUP_FAILED")
            cmd = ["release", "create", tag, "--verify-tag", "--draft",
                   "--target", manifest["git_commit"],
                   "--title", f"BliKVM v4 PiKVM {tag}", "--notes-file", str(note),
                   "--latest=false"]
            if manifest["prerelease"]:
                cmd.append("--prerelease")
            gh(*cmd)
            created = True
            view = gh("release", "view", tag, "--json", fields)
        remote = json.loads(view.stdout)
        if remote["isPrerelease"] != manifest["prerelease"]:
            raise policy.ReleaseBlocked("EXISTING_RELEASE_CHANNEL_CONFLICT")
        if (remote["tagName"] != tag or remote["targetCommitish"] != manifest["git_commit"]
                or remote["name"] != f"BliKVM v4 PiKVM {tag}" or remote["body"].strip() != notes(manifest).strip()):
            raise policy.ReleaseBlocked("EXISTING_RELEASE_METADATA_CONFLICT")
        by_name = {item["name"]: item for item in remote["assets"]}
        local = {path.name: path for path in dist.iterdir() if path.is_file()}
        if set(by_name) - set(local):
            raise policy.ReleaseBlocked("EXISTING_RELEASE_EXTRA_ASSET")
        for name, item in sorted(by_name.items()):
            destination = private / name
            gh("release", "download", tag, "--pattern", name, "--output", str(destination))
            if policy.digest(destination) != policy.digest(local[name]):
                raise policy.ReleaseBlocked("EXISTING_RELEASE_ASSET_CONFLICT")
        for name, path in sorted(local.items()):
            if name not in by_name:
                gh("release", "upload", tag, str(path))
        # Re-read every asset before publication or a successful retry.
        remote = json.loads(gh("release", "view", tag, "--json", fields).stdout)
        if {item["name"] for item in remote["assets"]} != set(local):
            raise policy.ReleaseBlocked("GITHUB_RELEASE_ASSET_SET_INCOMPLETE")
        if (remote["tagName"] != tag or remote["targetCommitish"] != manifest["git_commit"]
                or remote["name"] != f"BliKVM v4 PiKVM {tag}"
                or remote["body"].strip() != notes(manifest).strip()
                or remote["isPrerelease"] != manifest["prerelease"]):
            raise policy.ReleaseBlocked("GITHUB_RELEASE_METADATA_CHANGED")
        readback = private / "readback"
        readback.mkdir()
        for name, path in sorted(local.items()):
            downloaded = readback / name
            gh("release", "download", tag, "--pattern", name, "--output", str(downloaded))
            if policy.digest(downloaded) != policy.digest(path):
                raise policy.ReleaseBlocked("GITHUB_RELEASE_ASSET_READBACK_MISMATCH")
        prepublish.check(dist, tag, ref)
        if remote["isDraft"]:
            flags = ["release", "edit", tag, "--draft=false"]
            flags.append("--latest" if manifest["channel"] == "stable" else "--latest=false")
            gh(*flags)
        print(json.dumps({"result": "published" if created or remote["isDraft"] else "verified_existing",
                          "tag": tag, "assets": len(local)}))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dist", type=Path, required=True)
    parser.add_argument("--tag", required=True)
    parser.add_argument("--ref", required=True)
    args = parser.parse_args()
    publish(args.dist, args.tag, args.ref)


if __name__ == "__main__":
    main()
