#!/usr/bin/env python3
"""Match every shipped Debian package to its installed license document."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import posixpath
import re
import tarfile


HEADER = "package\tversion\tarchitecture\tdpkg_status\tsource\tlicense_document\tlicense_sha256\tlicense_terms"
CUSTOM_SOURCE = {"kvmd-video": "pikvm/kvmd", "kvmd-web": "pikvm/kvmd",
                 "ustreamer": "pikvm/ustreamer"}
# The kvmd-web package installs the upstream GPL text at its predecessor's
# documentation path. Keep this explicit until a new package revision fixes it.
DOCUMENT_OVERRIDE = {"kvmd-web": "usr/share/doc/kvmd-video/copyright"}
FREEFORM_TERMS = {
    "gcc-16-base": "GNU GPL and GCC exceptions; see full text",
    "libatomic1": "GNU GPL and GCC exceptions; see full text",
    "libgcc-s1": "GNU GPL and GCC exceptions; see full text",
    "libstdc++6": "GNU GPL and GCC exceptions; see full text",
    "libcrypt1": "LGPL-2.1-or-later and file-specific terms; see full text",
    "libgssapi-krb5-2": "MIT Kerberos and component terms; see full text",
    "libk5crypto3": "MIT Kerberos and component terms; see full text",
    "libkrb5-3": "MIT Kerberos and component terms; see full text",
    "libkrb5support0": "MIT Kerberos and component terms; see full text",
    "libpython3-stdlib": "Python Software Foundation and historical terms; see full text",
    "python3": "Python Software Foundation and historical terms; see full text",
    "python3-minimal": "Python Software Foundation and historical terms; see full text",
    "libtasn1-6": "LGPL-2.1-or-later and file-specific terms; see full text",
    "libxau6": "X11-style terms; see full text",
    "libxcb1": "MIT-style and component terms; see full text",
    "libxkbcommon0": "MIT/X11-style and component terms; see full text",
    "ubuntu-keyring": "GNU GPL for package material; archive keys excluded; see full text",
    "kvmd-video": "GNU GPL version 3 text; see upstream file notices",
    "kvmd-web": "GNU GPL version 3 text; see upstream file notices",
    "ustreamer": "GNU GPL version 3 text; see upstream file notices",
}


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def inventory(path: Path) -> list[tuple[str, str, str]]:
    rows = [tuple(line.split("\t")) for line in path.read_text().splitlines()]
    if (not rows or any(len(row) != 3 or not all(row) for row in rows)
            or len({row[0] for row in rows}) != len(rows)):
        raise ValueError("package inventory is malformed or duplicated")
    return rows


def status_records(data: bytes) -> dict[str, dict[str, str]]:
    records = {}
    for block in data.decode("utf-8").split("\n\n"):
        fields = {}
        for line in block.splitlines():
            if not line.startswith((" ", "\t")) and ": " in line:
                key, value = line.split(": ", 1)
                fields[key] = value
        if fields.get("Status") in ("install ok installed", "deinstall ok config-files"):
            name = fields["Package"]
            if name in records:
                raise ValueError(f"duplicate dpkg status: {name}")
            records[name] = fields
    return records


def rootfs_files(path: Path) -> tuple[dict[str, bytes], dict[str, str]]:
    """Read only the small status and copyright members of a rootfs tar/directory."""
    files: dict[str, bytes] = {}
    links: dict[str, str] = {}
    if path.is_dir():
        for member in (path / "usr/share/doc").iterdir():
            if member.is_symlink():
                links[member.relative_to(path).as_posix()] = member.readlink().as_posix()
        for member in (path / "usr/share/doc").glob("*/copyright"):
            relative = member.relative_to(path).as_posix()
            if member.is_symlink():
                links[relative] = member.readlink().as_posix()
            else:
                files[relative] = member.read_bytes()
        files["var/lib/dpkg/status"] = (path / "var/lib/dpkg/status").read_bytes()
    else:
        with tarfile.open(path, "r|gz") as archive:
            for member in archive:
                name = member.name.removeprefix("./")
                if name != "var/lib/dpkg/status" and not re.fullmatch(r"usr/share/doc/[^/]+(?:/copyright)?", name):
                    continue
                if member.issym():
                    links[name] = member.linkname
                elif member.isfile():
                    stream = archive.extractfile(member)
                    if stream is None:
                        raise ValueError(f"unreadable rootfs member: {name}")
                    files[name] = stream.read()
                elif name.endswith("/copyright"):
                    raise ValueError(f"invalid rootfs member: {name}")
    if "var/lib/dpkg/status" not in files:
        raise ValueError("rootfs has no dpkg status")
    return files, links


def document(name: str, files: dict[str, bytes], links: dict[str, str]) -> tuple[str, bytes]:
    path = DOCUMENT_OVERRIDE.get(name, f"usr/share/doc/{name}/copyright")
    current = path
    for _ in range(6):
        if current in files:
            return path, files[current]
        prefix = next((part for part in (current.rsplit("/", 1)[0], current)
                       if part in links), None)
        if prefix is None:
            raise ValueError(f"missing installed license document: {name} ({current})")
        target = links[prefix]
        suffix = current[len(prefix):].lstrip("/")
        current = posixpath.normpath(posixpath.join(posixpath.dirname(prefix), target, suffix))
        if not current.startswith("usr/share/doc/"):
            raise ValueError(f"license link escapes document tree: {name}")
    raise ValueError(f"license document link loop: {name}")


def terms(name: str, data: bytes) -> str:
    if name in FREEFORM_TERMS:
        return FREEFORM_TERMS[name]
    values = sorted(set(re.findall(r"^License:\s*(.+?)\s*$", data.decode("utf-8", "replace"), re.M)))
    if not values:
        raise ValueError(f"unreviewed free-form license document: {name}")
    return "; ".join(values)


def rows(package_list: Path, rootfs: Path) -> list[str]:
    packages = inventory(package_list)
    files, links = rootfs_files(rootfs)
    statuses = status_records(files["var/lib/dpkg/status"])
    if {name for name, _, _ in packages} != set(statuses):
        raise ValueError("package inventory differs from installed dpkg status")
    result = []
    for name, version, arch in packages:
        entry = statuses[name]
        if (entry["Version"], entry["Architecture"]) != (version, arch):
            raise ValueError(f"package version or architecture changed: {name}")
        path, data = document(name, files, links)
        if not data.strip():
            raise ValueError(f"empty license document: {name}")
        source = CUSTOM_SOURCE.get(name, entry.get("Source", name))
        values = (name, version, arch, entry["Status"], source, "/" + path, sha(data), terms(name, data))
        if any("\t" in value or "\n" in value for value in values):
            raise ValueError(f"invalid notice field: {name}")
        result.append("\t".join(values))
    return result


def verify(package_list: Path, rootfs: Path, notice_lock: Path) -> None:
    verify_inventory_lock(package_list, notice_lock)
    expected = HEADER + "\n" + "\n".join(rows(package_list, rootfs)) + "\n"
    if notice_lock.read_text() != expected:
        raise ValueError("package notice lock differs from exact rootfs")


def verify_inventory_lock(package_list: Path, notice_lock: Path) -> None:
    lines = notice_lock.read_text().splitlines()
    if not lines or lines[0] != HEADER:
        raise ValueError("package notice header is invalid")
    packages = inventory(package_list)
    if len(lines) - 1 != len(packages):
        raise ValueError("package notice count differs from inventory")
    for package, line in zip(packages, lines[1:]):
        fields = line.split("\t")
        if (len(fields) != 8 or tuple(fields[:3]) != package
                or fields[3] not in ("install ok installed", "deinstall ok config-files")
                or not fields[4] or not re.fullmatch(r"/usr/share/doc/[^/]+/copyright", fields[5])
                or not re.fullmatch(r"[0-9a-f]{64}", fields[6]) or not fields[7]):
            raise ValueError(f"invalid or unmatched package notice: {package[0]}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("generate", "verify"))
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--rootfs", type=Path, required=True)
    parser.add_argument("--lock", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "generate":
        args.lock.write_text(HEADER + "\n" + "\n".join(rows(args.inventory, args.rootfs)) + "\n")
    else:
        verify(args.inventory, args.rootfs, args.lock)


if __name__ == "__main__":
    main()
