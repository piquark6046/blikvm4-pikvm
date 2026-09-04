# Linux 7.x support assessment

Baseline inspected: upstream Linux v7.2, commit `8d3ae59288f1e7d58d76558a6ee96d533bc5019f`. Kernel.org listed v7.2.3 as current stable on 2026-09-03. The table distinguishes H616 support from support for this BliKVM carrier.

| Subsystem | Upstream support | Driver / Kconfig | DT work needed | Risk |
|---|---|---|---|---|
| ARM64 cores/PSCI | Yes | arm64 + TF-A PSCI | Board DTS/chosen only | LOW |
| H616 clocks | Yes | `clk-sun50i-h616`, `CONFIG_SUN50I_H616_CCU` | Reference CCU from `sun50i-h616.dtsi` | LOW |
| Resets | Yes, provided by CCU | same CCU driver | Reference reset IDs; no vendor integers | LOW |
| Main/R pinctrl and GPIO | Yes | `CONFIG_PINCTRL_SUN50I_H616`, `_R`; `CONFIG_GPIO_CDEV` | Board pin groups, line names, directions, and polarities | LOW |
| UART0/UART1 | Yes | `8250_dw`, `CONFIG_SERIAL_8250_DW` | Enable PH0/PH1 console; UART1/BT later | LOW |
| SD/MMC0 | Yes | `sunxi-mmc`, `CONFIG_MMC_SUNXI`; `allwinner,sun50i-h616-mmc` | Enable MMC0, PF6 card detect, 4-bit bus, supply | LOW |
| SDIO/MMC1 | Controller yes | same | Regulators/power-sequence and RTL8723DS child | MEDIUM |
| eMMC/MMC2 | Controller yes | `allwinner,sun50i-h616-emmc` | Leave disabled: no device observed | LOW |
| BliKVM Ethernet MAC | **Incomplete** | `dwmac-sun8i`, `CONFIG_DWMAC_SUN8I` | Upstream DTS/binding has H616 EMAC0 at `0x05020000`; this board uses EMAC1 at `0x05030000`. Add/validate EMAC1 compatible, syscon selector, IRQ 15, `CLK_BUS_EMAC1`, reset, RMII pin group, MDIO | HIGH |
| External 10/100 PHY | Generic Clause 22 works in vendor kernel | phylib | Identify PHY ID and any reset/power timing; PHY at address 0 | MEDIUM |
| USB host 1/2/3 | Yes | generic EHCI/OHCI platform, `CONFIG_USB_EHCI_HCD_PLATFORM`, `CONFIG_USB_OHCI_HCD_PLATFORM`, `CONFIG_PHY_SUN4I_USB` | Enable the wired ports and correct VBUS supplies | LOW |
| USB0 OTG/UDC | Yes | `musb-sunxi`, `CONFIG_USB_MUSB_SUNXI`; `allwinner,sun50i-h616-musb` | `dr_mode = "peripheral"`, PHY/extcon, USB-PC connector | LOW |
| Configfs composite gadget | Yes | `CONFIG_USB_CONFIGFS`, `CONFIG_USB_LIBCOMPOSITE` | Kernel config and userspace setup | LOW |
| HID gadget | Yes, but absent from stock arm64 defconfig | `CONFIG_USB_CONFIGFS_F_HID` / `usb_f_hid` | Explicitly enable in project config | LOW |
| Mass-storage gadget | Yes | `CONFIG_USB_CONFIGFS_MASS_STORAGE` / `usb_f_mass_storage` | Backing-store policy and safe detach | LOW |
| UVC capture host | Yes | `CONFIG_MEDIA_SUPPORT`, `CONFIG_VIDEO_DEV`, `CONFIG_USB_VIDEO_CLASS` | Stable udev name for `345f:2131` serial `29404080` | LOW |
| Capture audio | Yes | `CONFIG_SND_USB_AUDIO` | Optional policy | LOW |
| SPI0/SPI1 | Yes | `CONFIG_SPI_SUN6I`; H616/Sun8i-H3 compatible | Enable SPI1 and describe the real consumer | LOW |
| ST7789 LCD | Partial | `CONFIG_DRM_PANEL_SITRONIX_ST7789V` | Bli panel is 240x240 while the upstream panel driver's documented common mode is 240x320; validate controller variant/init/reset/DC before binding | MEDIUM |
| External RTC | Yes | `CONFIG_RTC_DRV_PCF8563`; `nxp,pcf8563` | Add I2C0 address 0x51 instead of runtime instantiation | LOW |
| Internal H616 RTC | Yes | `rtc-sun6i`; H616/H6 compatible | Keep available but external RTC should be preferred | LOW |
| Thermal sensors | Yes | `CONFIG_SUN8I_THERMAL`; `allwinner,sun50i-h616-ths` | Use calibration nvmem from SoC dtsi; fan policy later | LOW |
| Watchdog | Yes | `CONFIG_SUNXI_WATCHDOG` | Enable node/config | LOW |
| Crypto/RNG | Yes | `CONFIG_CRYPTO_DEV_SUN8I_CE`, `_TRNG`; kernel RNG | Config only | LOW |
| PMIC/regulators | Yes for AXP313A | `axp20x-i2c`, `CONFIG_MFD_AXP20X_I2C`, `CONFIG_REGULATOR_AXP20X`; `x-powers,axp313a` | Translate verified voltage rails; do not retain vendor `axp1530` spelling | MEDIUM |
| RTL8723DS Wi-Fi | Yes in v7.2 | `CONFIG_RTW88_8723DS`, SDIO + firmware | Add SDIO power sequence and firmware package | MEDIUM |
| RTL8723DS Bluetooth | Generic path exists | `CONFIG_BT_HCIUART`, H5/Realtek; `realtek,rtl8723ds-bt` | UART1 pins, flow control, enable/wake GPIOs, firmware | MEDIUM |

## Board-support conclusion

There is no `sun50i-h616-mangopi-mcore.dts` or BliKVM v4 DTB in upstream Linux v7.2. H616 core, SD, USB host, UDC, video, GPIO, PMIC, RTC, and wireless building blocks are present. The wired NIC is not a DTS-only exercise: v7.2 names/binds only H616 EMAC0 while the live carrier is wired to EMAC1. Linux 7.x is therefore feasible **with a focused EMAC1 kernel/binding patch and a new board DTS**. No vendor patch appears necessary for the initial UART+SD+initramfs boot.

## Initial configuration delta

Start from `arm64_defconfig`, then ensure at least:

```text
CONFIG_SERIAL_8250_DW=y
CONFIG_MMC_SUNXI=y
CONFIG_DWMAC_SUN8I=y
CONFIG_USB_MUSB_SUNXI=y
CONFIG_USB_CONFIGFS=y
CONFIG_USB_CONFIGFS_F_HID=y
CONFIG_USB_CONFIGFS_MASS_STORAGE=y
CONFIG_USB_VIDEO_CLASS=m
CONFIG_SND_USB_AUDIO=m
CONFIG_GPIO_CDEV=y
CONFIG_RTC_DRV_PCF8563=m
CONFIG_SUN8I_THERMAL=y
CONFIG_SUNXI_WATCHDOG=y
CONFIG_CRYPTO_DEV_SUN8I_CE=m
CONFIG_CRYPTO_DEV_SUN8I_CE_TRNG=y
CONFIG_RTW88_8723DS=m
```

Build v7.2.3 or a later 7.x stable point release, but re-run this delta check whenever the pinned version changes.
