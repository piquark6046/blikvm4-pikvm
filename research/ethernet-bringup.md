# Linux 7.2.3 Ethernet bring-up

Status: passed on hardware in two consecutive RAM-only Linux 7.2.3 boots.

## Pre-change evidence comparison

This comparison was completed before modifying the Linux driver, kernel
configuration, or board DT for this slice.

| Evidence | Captured vendor Linux 5.19.4 | Upstream Linux 7.2.3 | Minimum delta |
|---|---|---|---|
| MAC instance | `ethernet@5030000` probes as `dwmac-sun8i` | H616 DTSI describes only EMAC0 at `0x05020000` | Add the EMAC1 node at `0x05030000` |
| IRQ | GIC SPI 15; live IRQ is Linux IRQ 47 | EMAC0 uses GIC SPI 14 | Use GIC SPI 15 |
| clocks/reset | vendor IDs resolve to EMAC1 bus clock/reset | CCU already exports `CLK_BUS_EMAC1` and `RST_BUS_EMAC1` | Reference the existing symbolic IDs |
| pinctrl | PA0-PA9, function `emac1`, 40 mA | the pinctrl driver already exposes the same EMAC1 functions, but no group is defined in the DTSI | Add one board pin group for PA0-PA9 |
| interface mode | RMII | `dwmac-sun8i` supports RMII | Set `phy-mode = "rmii"` |
| MDIO/PHY | MDIO `stmmac-1`, PHY address 0, ID `0x00441400`, Generic PHY | no EMAC1 MDIO node or board PHY binding | Add MDIO and a generic Clause-22 PHY at address 0 |
| PHY supply/reset | vendor DT points `phy-supply` at always-on `vcc-sys`; no PHY reset GPIO is described; vendor log falls back only for the optional `phy-io` supply | the MMC slice already models U-Boot-established `vcc-sys` as fixed 3.3 V | Reuse that non-switchable supply; add no reset or delay guess |
| driver glue | vendor-era Armbian carries Andre Przywara's second-EMAC syscon-index patch and matches `allwinner,sun50i-h616-emac` | 7.2.3 has neither the compatible match nor the optional syscon index | Port only that focused patch and its binding update |

Primary local evidence is in `research/vendor-system/vendor.dts`,
`research/vendor-system/kernel.txt`, the extracted vendor config at
`out/build/vendor-5.19.4.config`, and the exact upstream 7.2.3 tree at
`out/src/linux-7.2.3/`. The vendor boot log shows a successful MAC probe and
later attaches `PHY [stmmac-1:00] driver [Generic PHY]`; it does not contain an
EMAC reset or MDIO timeout.

The vendor U-Boot control DT's stale PHY address 16 is not carried into Linux.
Linux address 0 comes independently from the captured vendor Linux DT and its
live `stmmac-1:00` PHY attachment. The hardware test must additionally archive
the Linux MDIO sysfs device and its `phy_id` before address 0 is accepted.

The first Linux 7.2.3 hardware run confirmed that independent check. Linux
enumerated `stmmac-0:00`, address `00`, ID `0x00441400`, and the exact DT path
`/soc/ethernet@5030000/mdio/ethernet-phy@0`. The ID is shared by X-Powers
AC200/AC300-family link PHYs, so the ID alone does not justify choosing a more
specific package binding. The captured vendor kernel also deliberately used
the generic Clause-22 driver. A proposed 2026 AC200/AC300 package driver exists,
but it is not part of Linux 7.2.3 and is not imported without hardware evidence
that the inherited generic configuration is insufficient.

## Patch provenance and risk

The driver portion is a direct 7.2.3 port of Andre Przywara's
`078f591017794a0ec689345b0eeb7150908cf85a`, also present in Armbian's 5.19
patch stack used by the vendor-kernel generation. It selects the second syscon
field from `syscon = <&syscon 1>` and adds the H616 compatible match. The local
patch also adds the missing H616 EMAC1 DTSI node and updates the current YAML
binding for the indexed phandle.

A 2026 Armbian report says the `syscon + 0x34` assumption fails on some other
H616/H618 boards. That report is a reason to retain reset-timeout evidence and
stop at the MAC-probe stage if it occurs; it does not override the captured
BliKVM vendor kernel's successful use of this patch family. No broader clock,
reset, internal-PHY, AC200/AC300, or regulator patch is included pre-emptively.

References:

- <https://github.com/apritzel/linux/commit/078f591017794a0ec689345b0eeb7150908cf85a>
- <https://lkml.iu.edu/2106.1/09144.html>
- <https://github.com/armbian/build/issues/10084>
- <https://lkml.iu.edu/2608.1/11530.html>

## Validation contract

`labctl boot-ethernet` must retain the existing serial-shell and read-only MMC
test, then archive the MAC probe, MDIO buses/devices, PHY ID and address, link,
addresses, carrier/speed/duplex, connected route, ping output, and final dmesg.
It configures only `192.168.88.2/24` on the target interface. It must not start
DHCP, add DNS or a default route, write storage, or persist U-Boot state.

## Hardware observations

Run `20260904T025854Z-792afb5-889995` reached every Ethernet stage through the
first target-to-host ICMP reply:

- the MAC probed without an EMAC/DMA reset timeout;
- the `stmmac-0` MDIO bus and PHY `stmmac-0:00` appeared;
- `eth0` negotiated 100 Mbps/full duplex and reported carrier and `LOWER_UP`;
- Linux installed only the connected `192.168.88.0/24` route after assigning
  `192.168.88.2/24`;
- the first reply from `192.168.88.1` arrived in 0.641 ms.

The original five-packet BusyBox process then waited indefinitely. This was
not a MAC, PHY, carrier, or IP-path stall: while that process was waiting, three
host-to-target probes all received replies (0% loss), and the kernel emitted no
MDIO, reset, DMA, watchdog, or TX-timeout error. The minimal allnoconfig kernel
had omitted `CONFIG_POSIX_TIMERS`; Linux consequently built `posix-stubs.o`
instead of `itimer.o`, leaving BusyBox ping without the alarm used to schedule
later probes. `CONFIG_POSIX_TIMERS=y` is therefore part of the minimal network
test support. Build run `20260904T030825Z-792afb5-282488` rebuilt the preserved
Linux 7.2.3 tree with three jobs and passed the DT schema and artifact checks.

`labctl` now runs five separately bounded one-packet probes, rejects a target
default route, and preserves partial command output plus a machine-readable
timeout record if the console command does not complete.

## Final hardware validation

Runs `20260904T035100Z-792afb5-231884` and
`20260904T035129Z-792afb5-102033` both passed the complete sequence from the
vendor U-Boot prompt through TFTP, Linux 7.2.3 initramfs, the existing MMC
read-only test, and Ethernet:

- `dwmac-sun8i` probed EMAC1 at `5030000.ethernet` without an EMAC/DMA reset
  timeout;
- Linux created MDIO bus `stmmac-0` and independently enumerated
  `stmmac-0:00`, PHY ID `0x00441400`, from DT node
  `/soc/ethernet@5030000/mdio/ethernet-phy@0`;
- `eth0` reached `carrier=1`, `operstate=up`, and `LOWER_UP` at 100 Mbps/full
  duplex;
- the target received only `192.168.88.2/24` and the connected
  `192.168.88.0/24` route; no DHCP, DNS, or default gateway was configured;
- each run completed five separately bounded pings to `192.168.88.1` with
  five replies and 0% loss, for 10/10 replies across the two boots;
- final Ethernet dmesg contained no persistent MDIO timeout, EMAC/DMA reset
  timeout, TX timeout, NETDEV watchdog, or stmmac DMA error; and
- MMC0 again enumerated and `/dev/mmcblk0p1` was mounted `ro,noload`, read, and
  unmounted without a storage write attempt.

The host isolation snapshot is archived in run
`20260904T035201Z-792afb5-246133`. The vendor U-Boot PHY address repair remains
session-only and is needed only to preserve the TFTP boot path. Linux does not
inherit it: the Linux DT directly binds address 0, verified by Linux MDIO
sysfs and both successful runtime attachments. Final build run
`20260904T035327Z-792afb5-084760` reused `out/build/linux-7.2.3` with three
jobs, performed no clean operation, passed the DT checks, and reproduced the
same tested Image, DTB, initramfs, and kernel-config hashes.
