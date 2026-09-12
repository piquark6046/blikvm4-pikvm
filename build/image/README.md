# P1 image tools

These tools assemble regular files under the repository's ignored `out/` tree.
They never accept a physical block-device output. They do not compile Linux,
packages or the accepted rootfs. Read `research/image-production-design.md` first.

Frozen inputs are in `inputs.lock.json`, traced to the accepted Run 04 artifact
record. Place the two extracted vendor bootloader files under `out/p1/vendor/`.
The private 4 MiB prefix can be checked with:

```
python3 build/image/verify-vendor.py out/p1/vendor/prefix-4MiB.bin
```

Each output directory must be new. Numeric owners require root; offline
validation attaches only a freshly created regular file, read-only, and mounts
it `ro,noload`. Run on the Build VM, with e2fsprogs 1.47.2, U-Boot tools 2025.10,
zstd 1.5.7 and the versions recorded in the manifest. Do not run in a container
that exposes writable physical media. No network is used by the assembler.

```
sudo python3 build/image/assemble.py --output out/p1/assembly-A
sudo python3 build/image/assemble.py --output out/p1/assembly-B
cmp out/p1/assembly-A/blikvm-v4-pikvm.img out/p1/assembly-B/blikvm-v4-pikvm.img
cmp out/p1/assembly-A/blikvm-v4-pikvm.img.zst out/p1/assembly-B/blikvm-v4-pikvm.img.zst
```

An assertion or command failure fails the gate and retains the output for
inspection. Never reuse a failed directory. The uncompressed image is fully
materialized: its hash covers exactly 1,077,936,128 bytes, including zeros.
Work files may be sparse; they are not published. Compression uses `-19 -T1`.
Only after both builds pass and compare, copy the public deliverables into
`out/images/`. Never copy the `work/` tree into public artifacts.

`filesystem-manifest.json` covers every intended entry, numeric owner/group,
mode, mtime, hardlink count, symlink target and regular-file content hash.
The manifest also includes the standard empty lost+found created by mkfs. Validation hashes
the source image before and after read-only inspection. SHA256SUMS covers the
image, compressed image and principal manifests.

The public image has locked accounts, empty authorized_keys, no temporary
serial autologin and no enrolled TLS/auth files. The accepted machine-id marker
and SSH key-generation service generate per-device state after boot.

`public-constants.json` accounts for exact, immutable upstream library self-test
vectors (OpenSSH fakepw, Passlib examples, GnuTLS known-answer keys). Exceptions
require both the full file hash and exact token hashes. Raw-image occurrence
counts must match those accepted filesystem files. These constants are not
credentials and must never be used for enrollment. Unknown material fails.

Offline private enrollment consumes the exact public image, not its staging
rootfs. Supply exactly the four paths from `assemble.ENROLL` beneath a private
input directory, with provenance.json containing `files: {path: {sha256, size}}`.
All provenance and file hashes stay private. For this P1 run the inputs were
extracted from the exact Run 04 enrolled initramfs's appended overlay; client
SSH and CA private keys were excluded. Target SSH host keys are generated on
first boot by the accepted service.

```
sudo python3 build/image/enroll.py --base out/images \
  --inputs out/p1/private/enrollment --output out/p1/private/enrolled
```

Enrollment validates certificate/key correspondence, name/IP and validity,
SSH public-key syntax, full image filesystem equality except the approved
four files and their necessary ssl parent directory, raw boot bytes and fsck.
The unchanged public base is re-hashed. Enrolled images and receipts remain
private. P2 must use the private receipt's enrolled-image hash, not the public
base hash. No flashing command is executed by these tools.

After both assemblies, run the supplemental exact enrollment-material check:

```
python3 build/image/verify-enrollment-separation.py \
  --enrollment out/p1/private/enrollment \
  out/p1/assembly-A/blikvm-v4-pikvm.img out/p1/assembly-B/blikvm-v4-pikvm.img
```

This rejects actual enrollment payloads and individual PEM/key lines anywhere
in the public raw bytes, and independently checks the accepted SSHA512 format.
It prints no private values or their hashes. Negative tests seed otherwise
unallocated bytes to prove both gates reject material outside filesystem paths.
