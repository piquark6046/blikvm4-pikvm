# BliKVM v4 hardware inventory

Research date: 2026-09-03. “Direct” means the connected board, not a similar product. The PCB/revision marking was not visually inspected, so the carrier revision remains unknown even though the live SoC and module identity are confirmed.

| Component | Identified part | Interface / wiring | Linux relevance | Evidence |
|---|---|---|---|---|
| SoC | Allwinner H616, ID `0x1823` | Quad Cortex-A53 | Mainline H616 family support exists | Direct TF-A/U-Boot and DT compatible |
| Compute module | MangoPi MCore | BliKVM carrier | No upstream BliKVM or MCore board DTS | Direct DT model `MangoPi Mcore`; official block diagram |
| DRAM | 1 GiB; DDR3L is probable | SoC DRAM controller | U-Boot SPL timing is board-critical | Direct SPL `1024 MiB` and Linux `1007700 kB`; MangoPi specifies DDR3L, but the package marking was not read |
| Boot storage | Removable 64 GB-class SDXC (`EC1S5`, 59.7 GiB); no active eMMC | MMC0, PF0-PF5, 4-bit; card detect PF6 active-low | Root is on SD; MMC2/eMMC disabled | Direct Linux/U-Boot; vendor DTS |
| Optional SPI boot | SPI0 NOR node exists; population unknown | SPI0 PC0/PC2/PC3/PC4 | Do not rely on it until `mtdinfo`/visual check | Vendor DTS; U-Boot reports zero flash size |
| Ethernet MAC | H616 second MAC at `0x05030000` | RMII on PA0-PA9 | Mainline 7.2 exposes only EMAC0; EMAC1 is the largest kernel gap | Direct U-Boot/Linux and vendor DTS |
| Ethernet PHY | Unidentified external 10/100 PHY, MDIO address 0 | RMII/MDIO; Linux binds `Generic PHY` | PHY ID and reset/power wiring must be captured with a live link | Direct `dmesg`, vendor DTS, vendor 100M specification |
| USB0 device | H616 MUSB UDC `0x05100000` | USB-PC connector; peripheral mode | PiKVM HID/MSD and probable FEL connector | Direct `/sys/class/udc`, vendor DTS and block diagram |
| USB1 host | EHCI/OHCI `0x05200000` | Permanently attached capture device | Standard UVC/audio host path | Direct USB topology and vendor DTS |
| Other USB hosts | EHCI/OHCI at `0x05310000` and `0x05311000` | At least one maps to external USB; exact carrier route not traced | Optional hardware | Vendor DTS and block diagram |
| HDMI capture | MacroSilicon MS2131 family, USB ID `345f:2131`, serial `29404080` | Internal USB2 high-speed; HDMI 1.4 input/loop-through on carrier | `uvcvideo` + `snd-usb-audio`; no CSI dependency | Direct target enumeration; official documentation calls it MS2131/MS2131B |
| UART bridge | QinHeng CH340/CH341 family, USB ID `1a86:7523`, revision 81.34 | BliKVM 5V USB-C to H616 UART0 PH0/PH1 | Console at 115200 8N1 | Direct host detection and console; vendor guide |
| Wi-Fi/Bluetooth | Realtek RTL8723DS | Wi-Fi on MMC1/SDIO PG0-PG5; Bluetooth on UART1 PG6-PG9 with PG16/17/19 control | Linux 7.2 has `rtw88_8723ds`; firmware and BT H5/Realtek configuration required | Direct vendor `8723ds` module; vendor DTS BT node; official block diagram |
| RTC | NXP PCF8563-compatible | I2C0 address `0x51`, backup cell/supercap | `rtc-pcf8563`, presently `/dev/rtc1`; should be in DTS | Direct live driver and I2C buses; vendor source and block diagram |
| PMIC/regulators | AXP313A-class, PMIC ID `0x4b` | R-I2C at address `0x36` | Mainline `x-powers,axp313a` support exists; regulator constraints must be translated | MangoPi specification; direct SPL ID; vendor DT calls the older equivalent `axp1530`; TF-A incorrectly attempts AXP305 over RSB and logs failure |
| LCD | Sitronix ST7789-family 240x240, 1.33 inch | SPI1: CS PH5, SCLK PH6, MOSI PH7; DC PI3; enable PI4; reset PI6 | Vendor uses userspace/spidev; upstream panel driver compatibility needs validation | Official BliKVM development table; vendor DTS only enables spidev |
| Front buttons/LED | SW1 PI1 high, SW2 PI2 high, activity LED PI5 low | GPIO | Move to gpio-keys/gpio-leds or line-name-based userspace | Official BliKVM development table/source |
| ATX control/status | power switch PH4 high; reset PI16 high; power LED PH10 high; HDD LED PH9 high | GPIO to ATX RJ45 circuitry | PiKVM ATX plugin must use libgpiod, not legacy global numbers | Official table and vendor source; historical globals 228/272/234/233 |
| Fan | PI13, active-high, software PWM in vendor app | GPIO | Prefer hwmon/thermal policy or conservative on/off first | Official table and vendor source; historical global 269 |
| Buzzer | PI15 active-high | GPIO | Optional | Official table; historical global 271 |

## Important conflicts and unknowns

- Marketing covers H616 and H313 variants, but this connected unit is positively H616.
- Exact BliKVM carrier revision, Ethernet PHY marking, SPI-NOR population, and DRAM chip marking remain unknown.
- Vendor DT compatible `x-powers,axp1530`, official module data says AXP313A, and Linux 7.2 uses `x-powers,axp313a`. Treat the vendor voltage rails as evidence but use the current binding.
- Vendor documentation alternates between “H.264 software encoding” and “MJPEG only.” Hardware inspection proves UVC MJPEG; H.264 is not an MS2131 capture format and would be a userspace transcode feature.
- Legacy global GPIO numbers are evidence of wiring, not an API contract. New code must resolve GPIO chip/offsets or DT line names and validate direction/polarity before driving outputs.

Primary raw evidence is in [vendor-system](vendor-system/README.md); external references are indexed in [sources.md](sources.md).

