# M7 Ubuntu Base builder (accepted RAM-root baseline)

Run on the AMD64 Build VM. Read `research/m7-ubuntu-rootfs-bringup.md`
for current hardware status and the preserved negative results. M6 is deferred.

Inputs are pinned in `versions.env`: Ubuntu Base 26.04.1 ARM64, the Canonical
CD-image signing fingerprint, a dated Ubuntu package snapshot, and the Debian
builder base digest and dated package snapshot. The Build VM's installed Ubuntu
keyring supplies trust; an archive cannot introduce its own trusted signer.
The rootfs package builder verifies signature, fingerprint, published checksum
and the independently pinned digest before extraction. Apt verifies signed
indexes and packages, uses an explicit CA bundle, and fails on index errors.

```sh
# Only necessary because documented systemd requirements are absent from M5:
./build/ubuntu/build-kernel.sh

# Fresh staging tree; retain/move a previous tree before a new package build.
./build/ubuntu/build.sh packages

# The public key input must resolve outside the repository:
./build/ubuntu/build.sh finalize /absolute/path/outside/repository/lab.pub
```

`packages` never compiles Linux. `build-kernel.sh` is the independent,
documented M7 exception and reuses the persistent incremental object directory.
Its shared input stamp forces correct reconfiguration when switching between
M5 and M7 without cleaning. Frozen M5 outputs are checked against
`m5-artifacts.sha256` before/after compilation; the M7 outputs go only to
`out/ubuntu/kernel/`. The board DTB and gadget descriptors/helpers are unchanged.
All drivers are built in, so no module installation or initramfs-tools is needed.

Emulation runs inside a separate user/mount/PID namespace created inside the
container. The script refuses the initial user namespace. Its binfmt_misc
registration contains textual hex escapes and checks that it cannot match the
native shell or emulator. Cleanup unregisters with a shell builtin before
detaching container-private mounts; no live host sysfs is exposed to packages.

Provisioning uses hostname `blikvm-m7`, systemd-networkd, `eth0` at
`192.168.88.2/24`, no DHCP/default route/IPv6 RA/link-local address, and a regular
`resolv.conf` with no DNS server. C.UTF-8 and UTC are explicit. An uninitialized
machine-id and packaged `sshd-keygen.service` create new identities per RAM boot.
SSH is public-key-only for `blikvm`; root login and password/keyboard-interactive
authentication are disabled. Serial `ttyS0` temporarily autologins the lab user,
which has passwordless sudo for hardware qualification. This is an isolated lab
image, not the final deployment access policy. No private key enters the builder.

The dedicated bridge key is outside Git at
`/home/user/.local/share/blikvm-m7/id_ed25519`; only its `.pub` file was transferred
to `/tmp/blikvm-m7-lab.pub` on the Build VM. Avoid copying that private key into
any artifact or evidence archive.

Outputs under `out/ubuntu/artifacts/` include a numeric-owner tarball, a
deterministic cpio/gzip RAM rootfs, Image/unchanged DTB/config, package-version
inventory, hashes, and a source/container/build manifest. Two fresh extractions/package installations produced byte-identical
tarball and cpio/gzip outputs; the package inventories also match. The current RAM image fits the qualified 64 MiB window. The filesystem
is writable RAM; no persistent root filesystem or recovery-SD write is required.

On the bridge, after transferring and verifying exact VM-produced bytes:

```sh
sudo python3 lab/ubuntu-boot.py --artifacts /path/to/m7/artifacts \
  --out-root /path/to/immutable/runs --require-lab-presets --boots 2
```

This command checks M7-B/C only. It cannot accept M7, substitute for
hardware regression tests, or declare the final 20-boot gate passed. It leaves
the serial console in a root shell for subsequent inspection/reboot.

If a failed RAM boot has neither SSH nor getty, `lab/ubuntu-recover.py` can wait
for an operator-initiated target power cycle and stop the vendor autoboot. It
does not operate a power relay or send persistent U-Boot commands. Recovery
boots never count toward the clean software reboot gate.

For M7-D, use a fresh successful Ubuntu boot (the frozen gadget setup refuses
to replace an existing gadget). Start the lab's bounded moving HDMI source,
then run:

```sh
sudo python3 lab/ubuntu-regressions.py --boot-result /path/to/boot.json \
  --out-root /path/to/runs
```

It checks the live boot ID against that boot's
archived identity before MMC, Ethernet, UVC and composite-gadget tests.
The stricter M7 wrapper rejects any startup error frame as well as stream errors.

For repeated boots, save the runner's JSONL output. Audit it separately:

```sh
python3 lab/ubuntu-reboot-gate.py --series /path/to/series.jsonl \
  --runs /path/to/runs --count 20
```
The auditor rejects omitted/intervening attempts, repeated boot IDs,
artifact changes, missing evidence, and breaks in the systemd-shutdown/U-Boot
chain. Counts 2 and 5 are staging gates; only count 20 sets the final reboot flag.
The reboot flag alone does not substitute for the separate hardware result.

The runner waits for systemd to reach `running` before sampling unit state; it
checks multi-user and serial getty separately and confirms running state again
through authenticated SSH. See the M7 record for the rejected early-snapshot batch.
