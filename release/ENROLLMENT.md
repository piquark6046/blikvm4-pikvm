# Offline enrollment

The public image has no shared web password, SSH authorization, or TLS key.
Download and verify the release assets, decompress the image, and extract
`blikvm-enroll.tar.gz` into a private directory on a Linux host. Keep
`release-manifest.json`, `filesystem-manifest.json`, `image-inputs.lock.json`,
and `bootloader-layout.json` beside the raw image. Install `zstd`,
`e2fsprogs`, `util-linux`, `fdisk`, `u-boot-tools`, `openssl`, and
`openssh-client`. Enrollment needs root for a read-only loop mount used to
verify the entire filesystem.

Create a TOML file with this shape, replacing every example value:

```toml
[network]
address = "192.0.2.20/24"
admin_cidr = "192.0.2.0/24"
hostname = "kvm.example.net"
# gateway = "192.0.2.1"   # optional
# dns = ["192.0.2.53"]    # optional

[auth]
admin_user = "operator"

[tls]
certificate = "/private/kvm-server.crt"
private_key = "/private/kvm-server.key"

[ssh]
# authorized_key = "/private/operator.pub"  # optional
```

The certificate must match the supplied hostname and target IP. Its private
key must not be group/world readable. The tool prompts twice for a new web
password; `--password-file /private/password` is available for automation when
that file is mode 0600. Passwords and TLS private keys are never placed in a
receipt. The tool rejects a public image that already contains enrollment
material and rejects filesystem changes outside its explicit allowlist.

```sh
zstd -d blikvm-v4-pikvm-<version>.img.zst -o blikvm-v4-pikvm-<version>.img
tar -xzf blikvm-enroll.tar.gz -C /private/blikvm-enroll
sudo python3 /private/blikvm-enroll/enroll.py \
  --base blikvm-v4-pikvm-<version>.img \
  --output /private/blikvm-v4-pikvm-my-device.img \
  --config /private/my-device.toml
```

The raw output and adjacent receipt are private. Verify the receipt's output
hash before flashing. The target will have no default route or DNS unless
the config explicitly supplies them. DHCP and mDNS remain disabled. Provide
the certificate chain to your browser through your normal trust process.
