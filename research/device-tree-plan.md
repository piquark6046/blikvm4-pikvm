# Device-tree plan

## Inputs and trust

1. Use upstream v7.2 `sun50i-h616.dtsi` as the SoC authority.
2. Use `sun50i-h616-orangepi-zero.dtsi` for UART/MMC/USB patterns and `sun50i-h616-bigtreetech-cb1.dtsi` for AXP313A regulator patterns.
3. Use the live decompiled [vendor DTS](vendor-system/vendor.dts) only for observed wiring/delta evidence.
4. Use the community `H616-mangopi` DTS only to discover leads. It is a decompiled vendor-style tree with non-upstream nodes and must not be copied.
5. Use BliKVM's official GPIO/LCD tables for carrier-only functions, then confirm line behavior on hardware before outputs are driven.

The new board should use a real board compatible such as `blicube,blikvm-v4`, followed by `allwinner,sun50i-h616`; upstream submission will also need a vendor prefix and board binding. The historical `mgcc,mangopi-mcore` compatible is useful evidence but is not registered upstream.

## Staged delta

| Stage | Required nodes/properties | Validation |
|---|---|---|
| First kernel boot | aliases/chosen UART0 115200; AXP313A on R-I2C at 0x36 with conservative vendor-confirmed rails; CPU supply; MMC0 PF0-PF5 + PF6 active-low card detect + 4-bit bus; watchdog/thermal inherited | `dtbs_check`; U-Boot `booti`; earlycon and normal console; SD partitions readable |
| Networking | New upstream-style EMAC1 SoC node at `0x05030000`; EMAC1 clock/reset/IRQ/syscon selector; PA0-PA9 RMII pin group; MDIO PHY address 0; supply/reset once identified | Driver probe without dummy supplies; PHY ID; carrier/link; static ping and SSH |
| PiKVM core | USB0 MUSB peripheral with PHY/extcon; USB1 EHCI/OHCI for internal `345f:2131`; any required VBUS fixed regulator; gpio-line-names for ATX/status; I2C0 PCF8563 | UDC name, composite enumeration, UVC 1080p30 stream, RTC read, non-destructive GPIO reads |
| Optional | MMC1 RTL8723DS Wi-Fi/power sequence, UART1 BT, SPI1 LCD, front buttons/LED, fan, buzzer, extra USB ports | One subsystem at a time; no PiKVM milestone dependency |
| Deferred | SoC HDMI/display-engine nodes, audio codecs not used by USB capture, SPI NOR boot, eMMC, GPU | Add only with a demonstrated product need |

## Minimum board facts from the live tree

- UART0: PH0/PH1, `serial@5000000`.
- MMC0: PF0-PF5, card detect PF6 active-low, 4-bit.
- MMC1/RTL8723DS: PG0-PG5, non-removable 4-bit SDIO; vendor kernel uses an out-of-tree `8723ds` module.
- Bluetooth UART1: PG6/PG7 + PG8/PG9 RTS/CTS; wake/enable lines PG16/PG17/PG19 require polarity review.
- Ethernet: EMAC1 `0x5030000`, RMII PA0-PA9, MDIO PHY 0.
- USB0: `0x5100000`, MUSB, peripheral.
- Capture USB host: EHCI/OHCI at `0x5200000`.
- SPI1: PH5 CS, PH6 clock, PH7 MOSI; carrier LCD sideband PI3/PI4/PI6.
- External RTC: I2C0 at 0x51 is currently instantiated by userspace, not vendor DTS.

## Rules for the implementation DTS

Use symbolic clock/reset/GPIO constants, current YAML bindings, and named regulators. Run `make dtbs_check` with the exact 7.x tree. Do not include decompiler phandles, vendor-only display/audio nodes, fake `rohm,dh2228fv` spidev compatibles, overclock OPPs, or unexplained delay values. Keep CPU frequency conservative for bring-up. The first DTS patch should intentionally omit ATX output driving and LCD.

