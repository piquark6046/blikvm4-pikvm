# Linux 7.x first hardware slice

Status: **passed on real BliKVM v4 hardware** on 2026-09-04. Linux 7.2.3
reaches `/init` and a command-verified interactive serial shell.

## Reproducible build

- Linux 7.2.3 is pinned to kernel.org SHA-256
  `8ba259e8e7b13ec6ef0941c8a39ad90b24bd4a4d6c0010ba6bafb794550ecd03`.
- Alpine 3.24.1 ARM64 minirootfs is pinned to SHA-256
  `f55a90f69052c5bd6f92cb09a8f47065970830b194c917a006fb94028e721259`.
- The Debian bookworm-slim base is pinned by OCI digest; the built toolchain
  image records its own content ID and includes dtschema 2026.6.
- `build/linux-serial.config` starts from `allnoconfig`. Required options were
  selected by extracting the config embedded in the known-good vendor 5.19.4
  Image. MMC, block, Linux Ethernet devices, USB, media, DRM, and modules are
  disabled.
- `out/build/linux-7.2.3/` is persistent. No build command calls `clean` or
  `mrproper`; default parallelism is three jobs.
- A no-change incremental build reproduced identical artifact hashes. The
  initramfs extraction also forces the pinned Alpine file modes, making its
  hash independent of the caller's umask.

The DTS describes only the H616 base, the verified 1 GiB memory window, and
UART0 on PH0/PH1. The local binding patch adds the BliCube vendor prefix,
`blicube,blikvm-v4` compatible, and DTB Makefile entry. Linux 7.2.3
`CHECK_DTBS=y` passes for the board DTB.

Latest corrected artifacts (build run
`20260904T014727Z-1900fd6-176003`):

| Artifact | Size | SHA-256 |
|---|---:|---|
| `Image` | 3,295,240 | `6b3d5f4d81f60951bf337e82cac1acef795c0e0311846280e1bedb865d6a59cd` |
| `sun50i-h616-blikvm-v4.dtb` | 19,119 | `cc1b42fc40a0cbf1f607945c26d3379b3a168854e3c346caa0f43b03a7888f0e` |
| `initramfs.cpio.gz` | 4,021,705 | `356a62d7b12b84d3a2bc85ed7c731d9f5d9742f83e0e1b8405f268074bdd1cc9` |

## Hardware attempts

`labctl boot-linux` copies every exact input into the run, writes
`SHA256SUMS`, atomically publishes a run-specific TFTP directory, checks all
three U-Boot byte counts, captures timestamped and raw UART, and classifies
the first failing stage.

| Run ID | Result | Evidence / correction |
|---|---|---|
| `20260904T011427Z-1900fd6-574146` | `network_load` failed | U-Boot ping passed; dnsmasq denied workspace SELinux labels preserved by `copy2`. Publisher now creates new files inheriting `tftpdir_rw_t`. |
| `20260904T011517Z-1900fd6-094415` | `kernel_boot` failed, `init_not_executable` | All TFTP byte counts passed. Linux 7.2.3 reached earlycon and ttyS0, detected the board, 1 GiB RAM and four CPUs, unpacked the initramfs, then reported `Failed to execute /init (error -8)`. |
| `20260904T014235Z-1900fd6-228052` | `/init` reached, then exited 127 | `BINFMT_SCRIPT` correction worked. Alpine BusyBox lacks the optional `cttyhack` applet, so `/init` was changed to execute BusyBox ash directly. |
| `20260904T014538Z-1900fd6-724315` | shell passed; verifier failed | The shell executed `uname` and emitted the verification marker. Its following prompt exposed an end-of-buffer-only regex, which now has regression coverage. |
| `20260904T014648Z-1900fd6-736450` | **passed** | U-Boot ping and all TFTP size checks passed; Linux reached `/init`; the serial shell returned `BLIKVM_SHELL_OK kernel=7.2.3-blikvm-v4-serial`; automated `dmesg` capture completed. |

The exact kernel cause was missing `CONFIG_BINFMT_SCRIPT` in the deliberately
minimal config. The corrected Image enables it. It also enables serial SysRq
and installs a serial rescue inittab so subsequent failures can be rebooted
without a power cycle.

The first failed image fell through to Alpine's stock BusyBox init, whose
serial getty is commented out. The physical reset recovered that one-time
state. `labctl` now also recovers safely when UART line-setup noise leaves the
vendor console at an unknown password prompt: it submits no credential until
it has established a fresh username prompt.

The passing shell reports that job control is unavailable because PID 1 has
explicit ttyS0 file descriptors but no controlling terminal; normal commands
and output are usable and were verified. No Linux storage or networking was
enabled. No SD/MMC data or persistent U-Boot environment was written.
