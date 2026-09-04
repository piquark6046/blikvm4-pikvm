# Linux 7.x serial and MMC bring-up build

The accepted baseline was limited to H616 core support, UART0, and an
Alpine/BusyBox initramfs. Incremental slices now add MMC0/read-only ext4,
EMAC1/RMII, and only the USB1 EHCI/PHY/VBUS path wired to the internal MS2131.
OHCI and the other USB controllers remain disabled, as do media/UVC, gadget,
UDC, USB storage, display, and board-control GPIO functions.

Build from the repository root:

```bash
./lab/labctl --pretty build-linux
```

The default is `-j3`; override it only when useful with `--jobs N` or
`LABCTL_JOBS=N`. The script never calls `make clean` or `make mrproper`.
Kernel objects and `.config` remain under `out/build/linux-7.2.3/`, and a
no-change rebuild reuses them.

Inputs are pinned in `versions.env`: the kernel.org Linux 7.2.3 archive,
Alpine 3.24.1 ARM64 minirootfs, their SHA-256 digests, and the Debian
bookworm-slim toolchain base digest. Downloads are verified before extraction.
The local toolchain image contains GCC 12.2, the kernel/DT build tools, and
pinned dtschema 2026.6. Every build validates the board DTB with the exact
Linux tree's schemas.

The config starts from `allnoconfig`, not the broad ARM64 defconfig. Its small
set of enabled options was cross-checked against the config embedded in the
known-good vendor 5.19.4 `Image`; the extracted vendor config is retained as
`out/build/vendor-5.19.4.config`. `build/linux-serial.config` is the reviewed
source of truth.

Current artifacts are written to `out/build/artifacts/`. Every `labctl`
build or boot also copies the exact artifacts, hashes, logs, and result JSON
into a unique `out/runs/<run-id>/` directory.

Boot and run the complete retained MMC, Ethernet, and USB-host tests with:

```bash
sudo ./lab/labctl --pretty boot-usb \
  --target-password-file /path/outside/repository/to/vendor-password
```

If the board is already stopped at U-Boot, replace the credential option with
`--no-reboot`. All U-Boot `setenv` operations are session-only. The command
publishes an immutable TFTP run directory, verifies every returned byte count,
captures raw and timestamped UART, waits for `BLIKVM_INITRAMFS_READY`, reruns
the read-only MMC/ext4 and isolated static-Ethernet checks, then archives USB
PHY/controller/VBUS evidence, `lsusb`, `lsusb -t`, VID:PID, topology, speed,
relevant dmesg, and a machine-readable result.
