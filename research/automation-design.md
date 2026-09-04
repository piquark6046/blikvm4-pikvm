# HIL automation design

## Interface

```bash
./lab/labctl detect
./lab/labctl uart
./lab/labctl build-linux
./lab/labctl boot-linux
./lab/labctl boot-mmc
./lab/labctl boot-ethernet
./lab/labctl boot-usb
./lab/labctl test
./lab/labctl cycle
./lab/labctl power-cycle
./lab/labctl fel
./lab/labctl collect
```

Every command writes one JSON document to stdout; human progress goes to stderr. The implementation includes `detect`, direct `uart` capture, `uboot exec`, `uboot collect`, `tftp-test`, `boot-vendor`, `build-linux`, `boot-linux`, `boot-mmc`, `boot-ethernet`, `boot-usb`, and host `collect`. The Linux boot commands atomically publish immutable artifacts, verify transfer sizes, retain prior-slice tests, capture per-device evidence and dmesg, and classify failures. Power/FEL mutation remains unimplemented and must fail explicitly rather than guess.

## Run model

```text
out/runs/<UTC timestamp>-<short commit>-<sequence>/
├── metadata.json
├── build.log
├── uart.log
├── uart.raw
├── uboot.log
├── dmesg.log
├── boot-console.log
├── test-results.json
├── Image
├── sun50i-h616-blikvm-v4.dtb
├── initramfs.cpio.gz
├── linux.config
├── manifest.json
└── SHA256SUMS
```

`metadata.json` records host/kernel/tool versions, source commits, container image digests, device identities, UART path, U-Boot version, load addresses, network configuration, artifact hashes, timestamps, and parent run. Files are append-only during a run and immutable after finalization.

Result schema:

```json
{
  "schema_version": 1,
  "result": "failed",
  "stage": "kernel_boot",
  "failure_signature": "Unable to mount root fs",
  "run_id": "20260903T120000Z-deadbee-000042",
  "uart_log": "out/runs/20260903T120000Z-deadbee-000042/uart.log"
}
```

Stages are `preflight`, `build`, `deploy`, `reboot`, `spl`, `tf_a`, `uboot_interrupt`, `network_load`, `kernel_boot`, `initramfs`, `ssh`, `test`, and `collect`. A result must identify the last passed stage and first failed stage.

## Components

- **Detector:** enumerate USB via sysfs, stable serial links, NIC carrier/routes, FEL VID:PID, toolchain/container tools, and block-device identities. It must distinguish the LattePanda `/dev/ttyACM0` from BliKVM UART.
- **Builder:** pinned privileged container only where required; separate Linux, DTB, initramfs, Ubuntu, and package targets; deterministic manifests and hashes.
- **UART engine:** direct termios/pyserial, exclusive file lock, raw timestamped byte log, bounded prompt state machine, one-second autoboot matcher, no terminal emulator scraping.
- **TFTP publisher:** per-run paths, atomic rename, bind server only to the lab NIC, verify sizes before telling U-Boot to load.
- **Boot controller:** use verified runtime variables and session-only `setenv`; stop on unexpected U-Boot version, address, prompt, or transfer size.
- **Target probe:** serial ready marker first, SSH second; collect kernel command line, dmesg, modules, DT identity, network, USB/V4L2/GPIO/RTC state.
- **Classifier:** deterministic patterns plus timeouts; retain unknown failures verbatim rather than forcing a misleading signature.

## Safety invariants

- Destructive media operations accept only a resolved `/dev/disk/by-id` plus expected serial/model/size and an explicit write flag. Never accept a bare `/dev/sdX` or `/dev/mmcblkX` as sufficient identity.
- The host boot device serial `0x979a962d` is permanently deny-listed for lab flashing.
- FEL access requires exactly one `1f3a:efe8` or an explicit device selector. SPI writes are a separate, approval-gated command.
- UART, TFTP state, power control, and each target are protected by locks so two cycles cannot race.
- Credentials/private keys are supplied at runtime from ignored paths or agents and are redacted from metadata/logs.
- No persistent `saveenv`; no bootloader write during kernel/userspace work.
- A watchdog timeout never automatically escalates to flash or power cycling.

No BliKVM power-control relay was detected. Its ATX output controls the remote computer, not the BliKVM itself. `power-cycle` must remain unavailable until a separately identified relay/PDU is installed and tested.
