# Allwinner FEL

## POSSIBLE BUT INCONVENIENT

The H616 BootROM implements FEL and upstream `sunxi-tools` identifies H616 as SoC ID `0x1823`. USB FEL uses `1f3a:efe8`. The vendor block diagram and live DTS both put the externally accessible USB-PC connector on USB0/MUSB, the controller BootROM FEL normally uses. This makes the electrical path plausible, but it was not proven: the board was never visible as `1f3a:efe8` during this pass, and `sunxi-fel` was not installed on the host.

### Why it is not the primary path

- Entering FEL likely requires removing/invalidating the SD boot image, a FEL SD helper, or an unidentified strap/button/test point. No documented BliKVM FEL button was verified.
- The USB-PC cable and 5V/UART cable are distinct roles; the UART cable does not expose FEL.
- A MangoPi MCore H616 report confirms `sunxi-fel version` and SPL start, but its U-Boot handoff timed out.
- As of 2026-09-03, upstream `sunxi-tools` still has open PR #236 for H616 secure-FEL SPL handoff and PR #248 for automatic SPL RAM FIT handoff. This is a warning that “device enumerates” and “reliably boots a full image” are different milestones.
- The existing vendor U-Boot already provides verified TFTP and `booti`, avoiding FEL handoff uncertainty.

### Safe test plan

1. Back up and preserve the known-good SD first.
2. Build current `sunxi-tools` at pinned revision and record the binary hash.
3. Power the board from 12 V, attach USB-PC to the lab host, and remove the SD (or use an expendable FEL-helper SD). Do not experiment on the known-good card.
4. Confirm exactly one `1f3a:efe8` device before invoking a tool.
5. Run read-only `sunxi-fel version` and `sunxi-fel sid`; save USB/UART logs.
6. Only after those pass, try a board-matched SPL/U-Boot in RAM while watching UART. Test both current upstream and the secure-handoff PR if the baseline stalls.
7. Never run `spiflash-write` until SPI population, backup, target identity, and recovery are established.

FEL may graduate to `RECOMMENDED RECOVERY PATH` after a repeatable RAM-only U-Boot boot on this exact carrier. Today, **known-good SD** is the recovery path.

