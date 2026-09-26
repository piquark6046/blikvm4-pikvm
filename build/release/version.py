#!/usr/bin/env python3
"""Strict public-release tag parsing and annotated-tag commit resolution."""

from __future__ import annotations

import argparse
import json
import re
import subprocess


NUM = r"(?:0|[1-9][0-9]*)"
BASE = rf"(?P<base>{NUM}\.{NUM}\.{NUM})"
STABLE = re.compile(rf"^{BASE}$", re.ASCII)
BETA = re.compile(rf"^{BASE}-beta\.(?P<number>{NUM})$", re.ASCII)
BUILD = re.compile(rf"^{BASE}-build\.(?P<short>[0-9a-f]{{8}})$", re.ASCII)
FULL_COMMIT = re.compile(r"^[0-9a-f]{40,}$", re.ASCII)


class InvalidTag(ValueError):
    pass


def resolve_commit(ref: str) -> str:
    if not ref or ref.startswith("-"):
        raise InvalidTag("invalid Git ref")
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--verify", f"{ref}^{{commit}}"], text=True
        ).strip()
    except subprocess.CalledProcessError as exc:
        raise InvalidTag("tag does not resolve to a commit") from exc


def short_commit(ref: str) -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short=8", f"{ref}^{{commit}}"], text=True
        ).strip()
    except subprocess.CalledProcessError as exc:
        raise InvalidTag("tag does not resolve to a short commit") from exc


def classify(tag: str, commit: str, short: str) -> dict[str, object]:
    if not FULL_COMMIT.fullmatch(commit) or not re.fullmatch(r"[0-9a-f]{8,}", short):
        raise InvalidTag("invalid resolved Git commit")
    match = STABLE.fullmatch(tag)
    channel = "stable"
    if match is None:
        match = BETA.fullmatch(tag)
        channel = "beta"
    if match is None:
        match = BUILD.fullmatch(tag)
        channel = "build"
    if match is None:
        raise InvalidTag("unsupported release tag")
    if channel == "build" and match.group("short") != short:
        raise InvalidTag("build suffix does not match tagged commit")
    return {
        "tag": tag,
        "version": tag,
        "base_version": match.group("base"),
        "channel": channel,
        "prerelease": channel != "stable",
        "git_commit": commit,
        "git_short_commit": short,
    }


def classify_ref(tag: str, ref: str) -> dict[str, object]:
    if ref != f"refs/tags/{tag}":
        raise InvalidTag("ref is not the exact tag")
    result = classify(tag, resolve_commit(ref), short_commit(ref))
    try:
        result["tag_object"] = subprocess.check_output(
            ["git", "rev-parse", "--verify", ref], text=True).strip()
    except subprocess.CalledProcessError as exc:
        raise InvalidTag("tag object cannot be resolved") from exc
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("check", "github-output"))
    parser.add_argument("tag")
    parser.add_argument("ref", nargs="?")
    parser.add_argument("--commit", help="local commit/ref for a check without a tag object")
    args = parser.parse_args()
    if args.command == "github-output":
        if args.commit or not args.ref:
            parser.error("github-output requires the full refs/tags/<tag> ref")
        record = classify_ref(args.tag, args.ref)
    elif args.commit:
        record = classify(args.tag, resolve_commit(args.commit), short_commit(args.commit))
    elif args.ref:
        record = classify_ref(args.tag, args.ref)
    else:
        # Stable and beta syntax can be checked without Git; build tags need a commit.
        if BUILD.fullmatch(args.tag):
            parser.error("build tags require --commit or the exact tag ref")
        record = classify(args.tag, "0" * 40, "0" * 8)
        record["git_commit"] = None
        record["git_short_commit"] = None
    print(json.dumps(record, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except InvalidTag as exc:
        raise SystemExit(f"INVALID_RELEASE_TAG: {exc}") from exc
