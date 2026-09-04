# UART, U-Boot, and TFTP bring-up result

Status: **PASS** on 2026-09-03. The host and target completed the required
known-good transport loop without a kernel build, boot-media write, or saved
U-Boot environment:

```text
vendor artifacts -> isolated host TFTP -> vendor U-Boot -> booti
                 -> vendor Linux 5.19.4 -> UART login prompt
```

## Preserved baseline

The accepted research was already committed as `1900fd6` (`research:
establish BliKVM v4 bring-up baseline`) and tagged `research-baseline`. The two
instruction documents remained untracked and were not included in that commit.

## Host network and service

The dedicated NetworkManager profile is `blikvm-lab` on `enp1s0`:

| Setting | Verified value |
|---|---|
| Host / target | `192.168.88.1/24` / `192.168.88.2/24` |
| Gateway / DNS | none / none |
| `ipv4.never-default` | `yes` |
| IPv6 | disabled |
| Link | detected, 100 Mb/s, full duplex, auto-negotiation on |
| Route | `192.168.88.0/24 dev enp1s0`; no lab default route |
| Internet / VPN | default route remained on `wlo1`; `wg_profile` remained up with a current handshake |

Firewalld has a dedicated `blikvm-lab` zone assigned only to `enp1s0`. It
allows the built-in `tftp` service, with forwarding and masquerading disabled.
`wlo1` and `wg_profile` remain in `FedoraWorkstation`.

The enabled `dnsmasq-blikvm-tftp.service` runs DNS-disabled dnsmasq, bound to
`enp1s0`/`192.168.88.1`, with `/var/lib/tftpboot` as its root. It runs in the
SELinux `dnsmasq_t` domain and serves files labeled `tftpdir_rw_t`. The service
uses about 1 MiB of RAM. Its source configuration is in `lab/`.

## UART and U-Boot automation

`labctl` now directly uses standard Python `termios` rather than pyserial or a
terminal emulator. It resolves the single `1a86:7523` device to its stable
`/dev/serial/by-id` path, configures 115200 8N1/no flow control, takes an
exclusive lock, timestamps RX/TX, detects Linux/login/U-Boot states, interrupts
the one-second autoboot, and stores per-run JSON plus UART/U-Boot logs.

Supported interfaces are:

```bash
./lab/labctl detect
sudo ./lab/labctl uart --seconds 10
sudo ./lab/labctl uboot exec 'version'
sudo ./lab/labctl uboot collect
sudo ./lab/labctl tftp-test
sudo ./lab/labctl boot-vendor
sudo ./lab/labctl collect
```

If the target is at `mangopimcore login:`, supply the OS credential through an
out-of-tree file with `--target-password-file` or
`LABCTL_TARGET_PASSWORD_FILE`. Password TX is recorded as `<redacted>`.

`labctl` rejects `saveenv`, `env save`, MMC/NAND writes or erases, and SPI
flash write/erase/update commands. No persistent target change was made.

## Collected real environment

The automated `uboot collect` run preserved `version`, `bdinfo`, full
`printenv`, `mmc list`, `mmc info`, the complete command list, command-specific
help for `booti`, `tftp`, `tftpboot`, `dhcp`, `ping`, `net`, and `usb`, plus
`net list`. Important verified values are:

| Variable/fact | Value |
|---|---|
| U-Boot | `2021.10-armbian`, built 2023-02-20 |
| DRAM | `0x40000000-0x7fffffff` (1 GiB) |
| `kernel_addr_r` | `0x40080000` |
| `fdt_addr_r` | `0x4FA00000` |
| `ramdisk_addr_r` | `0x4FF00000` |
| `scriptaddr` | `0x4FC00000` |
| `pxefile_addr_r` | `0x4FD00000` |
| `ipaddr` / `serverip` | absent until set for the current session |
| `boot_targets` | `fel mmc0 pxe dhcp` |
| MMC | one 59.7 GiB SD device |
| USB command | not compiled |

## Vendor U-Boot PHY defect and RAM-only recovery

The first ping failed with `Waiting for PHY auto negotiation ... TIMEOUT`
despite stable host carrier. Diagnostics proved:

- vendor U-Boot's embedded control DT declares `ethernet-phy@16`, `reg = 0x10`;
- the vendor Linux DT declares the EMAC1/RMII PHY at address `0`;
- Clause-22 registers at address `0` return PHY ID registers `0x0044:0x1400`
  and report link/auto-negotiation complete;
- U-Boot's attached `phy_device` held address `0x10`.

`labctl` contains a narrowly guarded workaround for this exact U-Boot build.
It verifies the version, control-DT mismatch, real PHY ID, U-Boot device
pointers, verified 1 GiB DRAM window, private structure layout, RMII mode, and
current bad value before changing the single in-RAM `phy_device.addr` word to
zero. The change is lost on every reset and is reapplied automatically. It does
not patch the SD bootloader, DTB, or environment. After the correction, U-Boot
immediately reported `host 192.168.88.1 is alive`.

## TFTP and known-good boot evidence

The small test file is exactly 39 bytes with SHA-256
`5e6fc42f65b3a83e369ca6cc63cfc735534ae2adb220ecf54a5c682d5ab77940`.
U-Boot transferred exactly 39 bytes into the verified `kernel_addr_r`.

The vendor kernel, legacy uInitrd, and base DTB were copied without modification
from the running read-only vendor system. Their paths, sizes, and hashes are in
`artifacts/vendor/README.md` and `SHA256SUMS`; the 34 MiB binaries are ignored by
Git but retained locally and published under `/var/lib/tftpboot/vendor/`.

The decisive run loaded all three files over TFTP at the real U-Boot addresses,
checked each returned byte count, installed the vendor root/console arguments,
ran the same `booti ${kernel_addr_r} ${ramdisk_addr_r} ${fdt_addr_r}` semantics,
and detected `mangopimcore login:` over UART.

Key run evidence under `out/runs/`:

| Run ID | Result |
|---|---|
| `20260903T125357Z-1900fd6-397912` | full U-Boot collection passed |
| `20260903T130300Z-1900fd6-785756` | 39-byte ping/TFTP proof passed |
| `20260903T131052Z-1900fd6-926188` | known-good vendor TFTP boot passed |
| `20260903T131247Z-1900fd6-257021` | login-to-U-Boot autonomous cycle and TFTP test passed |
| `20260903T131650Z-1900fd6-045269` | final host network/VPN/firewall/service collection passed |
| `20260903T131740Z-1900fd6-832635` | final vendor TFTP boot passed; target left at Linux login |

The failed runs are intentionally retained as diagnostic evidence for the PHY
address bug, SELinux service-domain correction, and prompt-matcher hardening.
