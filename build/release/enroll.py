#!/usr/bin/env python3
"""Enroll a downloaded public image offline without a shared credential."""

from __future__ import annotations

import argparse
import base64
import copy
import getpass
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import tomllib


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE if (HERE / "assemble.py").exists() else HERE.parent / "image"))
import assemble as A  # noqa: E402 - bundled beside this executable for public use


def regular(path: Path) -> None:
    if not stat.S_ISREG(path.lstat().st_mode):
        raise ValueError(f"expected regular file: {path}")


def config_data(path: Path) -> dict:
    regular(path)
    config = tomllib.loads(path.read_text())
    if set(config) != {"network", "auth", "tls", "ssh"}:
        raise ValueError("config sections must be network, auth, tls, ssh")
    net = config["network"]
    if set(net) - {"address", "admin_cidr", "hostname", "gateway", "dns", "allow_public_admin"}:
        raise ValueError("unknown network field")
    address = ipaddress.ip_interface(net["address"])
    allowed = ipaddress.ip_network(net["admin_cidr"], strict=True)
    if address.version != 4 or allowed.version != 4 or address.ip.is_multicast or address.ip.is_unspecified:
        raise ValueError("IPv4 unicast address and admin CIDR required")
    if allowed.prefixlen == 0 and net.get("allow_public_admin") is not True:
        raise ValueError("public admin CIDR requires allow_public_admin=true")
    host = net["hostname"]
    if not isinstance(host, str) or not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9.-]{0,251}[A-Za-z0-9])?", host):
        raise ValueError("invalid TLS hostname")
    gateway = net.get("gateway")
    if gateway is not None:
        gateway = ipaddress.ip_address(gateway)
        if gateway.version != 4 or gateway not in address.network:
            raise ValueError("gateway must be IPv4 on the target subnet")
    dns = [ipaddress.ip_address(item) for item in net.get("dns", [])]
    if any(item.version != 4 for item in dns):
        raise ValueError("DNS servers must be IPv4")
    auth = config["auth"]
    if set(auth) != {"admin_user"} or not re.fullmatch(r"[A-Za-z][A-Za-z0-9._-]{0,31}", auth["admin_user"]):
        raise ValueError("invalid admin user")
    tls = config["tls"]
    if set(tls) != {"certificate", "private_key"}:
        raise ValueError("TLS certificate and private_key are required")
    ssh = config["ssh"]
    if set(ssh) - {"authorized_key"}:
        raise ValueError("unknown SSH field")
    return {"address": address, "allowed": allowed, "hostname": host,
            "gateway": gateway, "dns": dns, "admin_user": auth["admin_user"],
            "cert": Path(tls["certificate"]).expanduser().resolve(),
            "key": Path(tls["private_key"]).expanduser().resolve(),
            "ssh_key": Path(ssh["authorized_key"]).expanduser().resolve() if ssh.get("authorized_key") else None}


def run(*arguments: str) -> bytes:
    return subprocess.run(arguments, check=True, capture_output=True,
                          stdin=subprocess.DEVNULL).stdout


def supplied_tls(data: dict) -> None:
    regular(data["cert"])
    regular(data["key"])
    if data["key"].stat().st_mode & 0o077:
        raise ValueError("TLS private key must not be group/world readable")
    if run("openssl", "x509", "-in", str(data["cert"]), "-pubkey", "-noout") != run(
        "openssl", "pkey", "-in", str(data["key"]), "-pubout"
    ):
        raise ValueError("TLS certificate/key mismatch")
    for kind, value, label in (("-checkhost", data["hostname"], "hostname"),
                               ("-checkip", str(data["address"].ip), "address")):
        checked = subprocess.run(["openssl", "x509", "-in", str(data["cert"]),
                                  "-noout", kind, value], capture_output=True)
        if checked.returncode or b"does match" not in checked.stdout:
            raise ValueError(f"TLS certificate {label} mismatch")
    run("openssl", "x509", "-in", str(data["cert"]), "-noout", "-checkend", "86400")


def ssh_material(path: Path | None) -> bytes | None:
    if path is None:
        return None
    regular(path)
    value = path.read_bytes().strip()
    if b"\n" in value or not re.fullmatch(rb"(?:ssh-ed25519|ecdsa-sha2-nistp(?:256|384|521)|ssh-rsa) [A-Za-z0-9+/=]+(?: [^\r\n]+)?", value):
        raise ValueError("expected one SSH public key")
    run("ssh-keygen", "-l", "-f", str(path))
    return value + b"\n"


def password_bytes(path: Path | None) -> bytes:
    if path:
        regular(path)
        if path.stat().st_mode & 0o077:
            raise ValueError("password file must be mode 0600")
        value = path.read_bytes().removesuffix(b"\n")
    else:
        first = getpass.getpass("New web admin password: ")
        second = getpass.getpass("Repeat web admin password: ")
        if first != second:
            raise ValueError("passwords did not match")
        value = first.encode()
    if len(value) < 12 or any(byte < 0x20 or byte == 0x7f for byte in value):
        raise ValueError("admin password must be at least 12 bytes with no control bytes")
    return value


def replacements(data: dict, password: bytes, read_base) -> dict[str, tuple[bytes, int, int, int]]:
    salt = os.urandom(16)
    digest = hashlib.sha512(password + salt).digest() + salt
    htpasswd = data["admin_user"].encode() + b":{SSHA512}" + base64.b64encode(digest) + b"\n"
    address = str(data["address"].ip)
    network = ("[Match]\nName=eth0\n[Network]\n"
               f"Address={data['address']}\nConfigureWithoutCarrier=yes\nDHCP=no\n"
               "LinkLocalAddressing=no\nIPv6AcceptRA=no\nLLMNR=no\nMulticastDNS=no\n"
               + (f"Gateway={data['gateway']}\n" if data["gateway"] else ""))
    network += "[Link]\nRequiredForOnline=routable\n"
    nft = ("add table ip blikvm_lab\nflush table ip blikvm_lab\n"
           "table ip blikvm_lab {\n chain input { type filter hook input priority 0; policy drop;\n"
           f" iifname \"eth0\" ip saddr {data['allowed']} ip daddr {address} tcp dport {{ 22, 443 }} accept\n"
           f" iifname \"eth0\" ip saddr {data['allowed']} ip daddr {address} ip protocol icmp accept\n"
           " iifname \"lo\" accept\n counter drop\n }\n"
           " chain forward { type filter hook forward priority 0; policy drop; }\n}\n")
    nginx = read_base("etc/kvmd/nginx/nginx.conf")
    if nginx.count(b"listen 192.168.88.2:443 ssl;") != 1 or nginx.count(b"server_name blikvm-v4.lab 192.168.88.2;") != 1:
        raise ValueError("unexpected public nginx template")
    nginx = nginx.replace(b"listen 192.168.88.2:443 ssl;", f"listen {address}:443 ssl;".encode())
    nginx = nginx.replace(b"server_name blikvm-v4.lab 192.168.88.2;", f"server_name {data['hostname']} {address};".encode())
    sshd = read_base("etc/ssh/sshd_config.d/00-blikvm-lab.conf")
    if sshd.count(b"ListenAddress 192.168.88.2") != 1:
        raise ValueError("unexpected public SSH template")
    sshd = sshd.replace(b"ListenAddress 192.168.88.2", f"ListenAddress {address}".encode())
    values = {
        "etc/kvmd/htpasswd": (htpasswd, 0o400, 988, 0),
        "etc/kvmd/nginx/ssl/server.crt": (data["cert"].read_bytes(), 0o644, 0, 0),
        "etc/kvmd/nginx/ssl/server.key": (data["key"].read_bytes(), 0o600, 0, 0),
        "etc/systemd/network/10-lab.network": (network.encode(), 0o644, 0, 0),
        "etc/kvmd/access.nft": (nft.encode(), 0o644, 0, 0),
        "etc/kvmd/nginx/nginx.conf": (nginx, 0o644, 0, 0),
        "etc/ssh/sshd_config.d/00-blikvm-lab.conf": (sshd, 0o644, 0, 0),
        "etc/hostname": (data["hostname"].split(".")[0].encode() + b"\n", 0o644, 0, 0),
        "etc/hosts": (f"127.0.0.1 localhost\n127.0.1.1 {data['hostname'].split('.')[0]}\n".encode(), 0o644, 0, 0),
        "etc/resolv.conf": (("".join(f"nameserver {server}\n" for server in data["dns"]) or
                             "# No DNS server enrolled.\n").encode(), 0o644, 0, 0),
    }
    key = ssh_material(data["ssh_key"])
    if key is not None:
        values["home/blikvm/.ssh/authorized_keys"] = (key, 0o600, 1000, 1000)
    return values


def enroll(base: Path, output: Path, config: Path, password_file: Path | None) -> None:
    if os.geteuid() != 0:
        raise ValueError("root is required for read-only loop validation")
    os.umask(0o077)
    regular(base)
    output = output.absolute()
    if output.exists() or output.is_symlink() or base.resolve() == output.resolve():
        raise ValueError("output must be a new regular-image path")
    data = config_data(config)
    supplied_tls(data)
    password = password_bytes(password_file)
    release = json.loads((base.parent / "release-manifest.json").read_text())
    expected_sha = release["public_image"]["sha256"]
    if A.digest(base) != expected_sha:
        raise ValueError("base image does not match release manifest")
    expected = json.loads((base.parent / "filesystem-manifest.json").read_text())
    lock = json.loads((base.parent / "image-inputs.lock.json").read_text())
    layout = json.loads((base.parent / "bootloader-layout.json").read_text())
    for filename, field in (("filesystem-manifest.json", "filesystem_manifest_sha256"),
                            ("image-inputs.lock.json", "release_input_lock_sha256")):
        if A.digest(base.parent / filename) != release[field]:
            raise ValueError(f"release manifest does not bind {filename}")
    layout_item = release["artifacts"]["bootloader-layout.json"]
    if A.digest(base.parent / "bootloader-layout.json") != layout_item["sha256"]:
        raise ValueError("release manifest does not bind bootloader layout")
    with tempfile.TemporaryDirectory(prefix=".blikvm-enroll-", dir=output.parent) as temporary:
        work = Path(temporary)
        (work / "base-check").mkdir()
        A.validate(base, work / "base-check", expected, lock, layout)
        image = work / "enrolled.img"
        shutil.copyfile(base, image)
        fs = work / "root.ext4"
        with image.open("rb") as stream, fs.open("xb") as target:
            stream.seek(A.OFFSET)
            shutil.copyfileobj(stream, target, 1024**2)

        def read_base(name: str) -> bytes:
            return run("debugfs", "-R", f"cat /{name}", str(fs))

        values = replacements(data, password, read_base)
        old = copy.deepcopy(expected)
        directory = "etc/kvmd/nginx/ssl"
        if directory in expected:
            raise ValueError("base image already has an SSL enrollment directory")
        expected[directory] = {"mode": 0o755, "uid": 0, "gid": 0, "mtime": A.EPOCH, "type": stat.S_IFDIR}
        commands = [f"mkdir /{directory}"]
        changed = [directory]
        for index, (name, (payload, mode, uid, gid)) in enumerate(values.items()):
            local = work / f"input-{index}"
            if any(character in str(local) for character in ('"', '\n', '\r')):
                raise ValueError("output path cannot be represented in the enrollment batch")
            local.write_bytes(payload)
            if name in old:
                commands.append(f"rm /{name}")
            commands.append(f'write "{local}" /{name}')
            expected[name] = {"mode": mode, "uid": uid, "gid": gid, "mtime": A.EPOCH,
                              "type": stat.S_IFREG, "nlink": 1, "size": len(payload),
                              "sha256": hashlib.sha256(payload).hexdigest()}
            changed.append(name)
        for name in changed:
            item = expected[name]
            for field, value in (("mode", item["type"] | item["mode"]), ("uid", item["uid"]),
                                 ("gid", item["gid"]), ("generation", 0)):
                commands.append(f"set_inode_field /{name} {field} {value}")
            for field in ("mtime", "atime", "ctime", "crtime"):
                commands.append(f"set_inode_field /{name} {field} @{A.EPOCH}")
                commands.append(f"set_inode_field /{name} {field}_extra 0")
        batch = work / "enroll.debugfs"
        batch.write_text("\n".join(commands) + "\n")
        result = A.run(["debugfs", "-w", "-f", batch, fs])
        if result.stderr.decode().splitlines()[1:]:
            raise ValueError("debugfs reported an enrollment error")
        with image.open("r+b") as target, fs.open("rb") as source:
            target.seek(A.OFFSET)
            shutil.copyfileobj(source, target, 1024**2)
            target.flush()
            os.fsync(target.fileno())
        actual = sorted(name for name in set(old) | set(expected) if old.get(name) != expected.get(name))
        if actual != sorted(changed):
            raise ValueError("enrollment mutation exceeded the approved allowlist")
        (work / "enrolled-check").mkdir()
        A.validate(image, work / "enrolled-check", expected, lock, layout, enrolled=True)
        if A.digest(base) != expected_sha:
            raise ValueError("base image changed during enrollment")
        result_sha = A.digest(image)
        os.replace(image, output)
    receipt = {
        "schema_version": 1, "base_image_sha256": expected_sha,
        "output_image_sha256": result_sha, "changed_paths": actual,
        "tls_certificate_sha256": A.digest(data["cert"]),
        "tls_certificate_bytes": data["cert"].stat().st_size,
        "ssh_public_key_sha256": A.digest(data["ssh_key"]) if data["ssh_key"] else None,
        "ssh_public_key_bytes": data["ssh_key"].stat().st_size if data["ssh_key"] else None,
        "network": {"address": str(data["address"]), "admin_cidr": str(data["allowed"]),
                    "hostname": data["hostname"], "gateway": str(data["gateway"]) if data["gateway"] else None,
                    "dns": [str(item) for item in data["dns"]]},
        "source_commit": release["git_commit"], "enrollment_tool_version": 1,
        "enrollment_tool_sha256": A.digest(Path(__file__)), "physical_media_written": False,
    }
    (output.parent / (output.name + ".receipt.json")).write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"result": "passed", "output": str(output), "sha256": result_sha}))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--password-file", type=Path)
    args = parser.parse_args()
    enroll(args.base, args.output, args.config, args.password_file)


if __name__ == "__main__":
    main()
