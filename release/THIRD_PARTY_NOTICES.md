# Third-party source and notices

This release contains a source-built Linux boot chain and an Ubuntu ARM64
userspace. `package-inventory.tsv` lists every dpkg record in the image.
`package-notices.tsv` has one matching row for each record: exact package
version and architecture, dpkg state, source package, installed license
document path, SHA-256 of that document, and its license labels or a pointer to
the full free-form terms. The documents are included in the image under
`/usr/share/doc/`. The build verifies the table against the rootfs archive;
both independent builders must agree. One record, `kvmd-video`, is retained by
dpkg in `deinstall ok config-files` state after replacement by `kvmd-web`.
The `kvmd-web` payload installs its upstream GPL text at
`/usr/share/doc/kvmd-video/copyright`; this shared path is explicit in the
table. The exact source versions and upstream archive hashes are in
`source-manifest.json` and `image-inputs.lock.json`.

## Ubuntu packages

The package source names and versions are in `package-notices.tsv`; the
corresponding packages and source records come from the pinned
[Ubuntu archive snapshot](https://snapshot.ubuntu.com/ubuntu/20260906T000000Z/).
Package-specific copyright and license terms are the exact files at the
paths and hashes in the table. Many packages contain files under more than one
license; a table summary never replaces the full installed document.

## Source-built components

| Component | Exact source | License and notices |
| --- | --- | --- |
| Linux 7.2.3 kernel | [kernel.org tarball](https://cdn.kernel.org/pub/linux/kernel/v7.x/linux-7.2.3.tar.xz), SHA-256 `8ba259e8e7b13ec6ef0941c8a39ad90b24bd4a4d6c0010ba6bafb794550ecd03` | `COPYING` and per-file SPDX notices; kernel `COPYING` identifies GPL-2.0 with Linux-syscall-note. |
| U-Boot SPL and main bootloader | [U-Boot commit 88dc2788777babfd6322fa655df549a019aa1e69](https://github.com/u-boot/u-boot/tree/88dc2788777babfd6322fa655df549a019aa1e69) | `COPYING`, `Licenses/`, and per-file SPDX notices; the project README identifies GPL-2.0-or-later for its main text. |
| Trusted Firmware-A BL31 | [TF-A commit 1d5aa939bc8d3d892e2ed9945fa50e36a1a924cc](https://github.com/ARM-software/arm-trusted-firmware/tree/1d5aa939bc8d3d892e2ed9945fa50e36a1a924cc) | `docs/license.rst` identifies BSD-3-Clause and names included components with other terms. |
| uStreamer 6.65 | [uStreamer commit db87e03ce769d06ba62314ca7537e1cb3369b4de](https://github.com/pikvm/ustreamer/tree/db87e03ce769d06ba62314ca7537e1cb3369b4de) | Upstream `LICENSE`, installed at `/usr/share/doc/ustreamer/copyright`, contains GPL version 3 text; retain source-file notices. |
| kvmd 4.213 and its web assets | [kvmd commit 387846d22fa807f97de09750c32c1c9b26d36c1c](https://github.com/pikvm/kvmd/tree/387846d22fa807f97de09750c32c1c9b26d36c1c) | Upstream `LICENSE`, installed at `/usr/share/doc/kvmd-video/copyright`, contains GPL version 3 text; retain source-file and web-asset notices. |

The board DTS, kernel and application patches, packaging, service units, and
build scripts used for this image are in the tagged repository source. File
headers and the originating upstream terms govern copied or adapted material;
the repository's root `LICENSE` governs project-authored material. The image
uses the source-built U-Boot/TF-A bytes identified by `bootloader-layout.json`;
it does not redistribute the private recovery-card bootloader.
