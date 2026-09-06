# BliKVM v4 PiKVM Port — Codex Working Instructions

## Mission

Continue the existing BliKVM v4 Allwinner H616 PiKVM port from the
current repository state.

Do not restart the project from scratch.

The repository already contains verified research, implementation,
hardware evidence, automated tests, and accepted Linux 7.2.3 bring-up
milestones.

Read the existing repository documentation before making changes.

## Architecture

There are three roles:

### Build machine

This repository is checked out on the current Ubuntu 26.04.1 AMD64 VM:

    ~/repos/blikvm4-pikvm

This VM is the build and development plane.

Perform here:

- source editing
- Git operations
- Linux compilation
- DTB compilation
- initramfs construction
- rootfs construction
- Docker builds
- static/unit tests
- artifact hashing
- research/documentation updates

The VM has substantially more CPU and RAM than the lab controller.
Do not perform heavy compilation on the bridge machine.

### Bridge / HIL machine

A LattePanda 3 Delta running Ubuntu 26.04.1 Server is available through
the configured ssh-mcp MCP server.

The bridge machine is the hardware-control plane.

Use it for:

- BliKVM UART
- U-Boot interaction
- TFTP serving
- target Ethernet
- USB host-side inspection
- BliKVM USB-PC enumeration testing
- optional FEL experiments
- hardware logs
- physical deployment and HIL testing

Use the configured ssh-mcp tools rather than assuming local access to
the hardware.

### Target

The target is the Allwinner H616 BliKVM v4.

The known-good vendor SD remains the recovery path.

Do not replace U-Boot or permanently modify the U-Boot environment.

## Repository state

Before doing new work, read at least:

- research/README.md
- research/milestones.md
- research/decision.md
- research/usb-gadget.md
- research/uvc-v4l2-bringup.md
- research/automation-design.md
- build/README.md
- lab/labctl
- tests/test_labctl.py

Also inspect:

    git status
    git log --oneline --decorate -20
    git tag --sort=-creatordate
    git remote -v

Do not assume old conversational context is more authoritative than
the checked-in repository and archived hardware evidence.

## Accepted baseline

Do not redo these milestones unless a regression requires it:

- UART / U-Boot / TFTP
- Linux 7.2.3 serial initramfs
- MMC0 and read-only ext4
- H616 EMAC1 / RMII Ethernet
- internal USB1 EHCI host
- MS2131 enumeration
- upstream UVC/V4L2
- real bounded video capture

The accepted build is incremental.

Never routinely run:

    make clean
    make mrproper

and do not delete the persistent Linux build directory merely to solve
an ordinary compilation problem.

## Current milestone

Continue with M5: Linux 7.2.3 USB gadget / UDC bring-up.

The vendor system already proves that the physical USB-PC path,
H616 USB0 MUSB controller, configfs HID, mouse modes and mass-storage
gadget are viable.

The project Linux 7.2.3 baseline has not yet brought this path up.

Start with the smallest slice:

    H616 USB0
      -> PHY0
      -> MUSB UDC
      -> /sys/class/udc
      -> configfs/libcomposite
      -> one HID keyboard
      -> enumeration on the LattePanda USB host

Do not jump directly to the final PiKVM composite gadget.

## Required M5 progression

Proceed in this order:

1. Enable and verify PHY0 and MUSB peripheral/UDC support.
2. Verify the expected UDC appears under /sys/class/udc.
3. Create and bind one minimal configfs HID keyboard gadget.
4. Verify enumeration from the LattePanda host.
5. Verify clean unbind/rebind and physical reconnect.
6. If stable, test one deterministic harmless HID report.
7. Preserve concurrent MS2131 UVC capture while the gadget is active.
8. Reproduce the result across at least two RAM-only boots.
9. Only then add:
   - absolute mouse
   - relative mouse
10. Only after HID modes pass, add a disposable read-only mass-storage
    backing image.

Do not begin GPIO/ATX, Ubuntu final rootfs, uStreamer or kvmd until M5
is accepted.

## ssh-mcp usage

At the start of a hardware task:

1. Discover/verify the configured bridge connection.
2. Verify the remote identity using read-only commands such as:
   - hostname
   - uname -a
   - ip -br addr
   - lsusb
   - ls -l /dev/serial/by-id
3. Locate the existing BliKVM UART stable path.
4. Verify the TFTP root and lab network configuration.
5. Do not assume the bridge machine filesystem layout without checking it.

Use SFTP upload/download facilities where practical for artifact and
evidence transfer.

Build artifacts must originate from the Build VM.

Typical direction:

    Build VM
      -> build Image / DTB / initramfs
      -> upload to bridge
      -> bridge publishes via TFTP
      -> bridge controls U-Boot/UART
      -> target boots
      -> bridge performs host-side USB tests
      -> evidence is downloaded back to Build VM

Do not copy compiler toolchains to the bridge unnecessarily.

## Hardware evidence

Every hardware run must archive enough evidence to understand failures.

Preserve at least:

- run metadata
- exact Git commit / dirty state
- artifact SHA-256 hashes
- UART log
- U-Boot log
- target dmesg
- /sys/class/udc
- relevant target USB/MUSB/PHY messages
- configfs gadget state
- host lsusb
- host lsusb -t
- host USB/HID dmesg
- USB descriptors
- bounded UVC regression result
- machine-readable test result

Prefer immutable per-run directories.

## Regression policy

Every new hardware slice must preserve previously accepted functionality.

For M5, USB gadget success is not accepted if it breaks:

- serial boot
- MMC
- Ethernet
- internal MS2131 USB host
- V4L2/UVC capture

In particular, verify simultaneously:

    USB1 EHCI -> MS2131 -> bounded video capture

and

    USB0 MUSB -> HID gadget -> LattePanda enumeration

## Git policy

Work from the existing history.

Before changing anything:

    git fetch --all --tags
    git status
    git log --oneline --decorate -20

Do not rewrite accepted baseline history.

Commit coherent, experimentally verified slices.

Do not commit:

- GitHub PATs
- Codex credentials
- SSH private keys
- VPN credentials
- passwords
- arbitrary large raw logs unless intentionally selected as evidence

Before pushing, review:

    git diff --cached
    git status

The configured GitHub credential is intentionally scoped to this
repository.

## Failure behavior

Do not add more features to work around a basic failure.

If USB gadget bring-up fails, isolate the failure among:

- device tree
- USB0 controller
- PHY0
- clocks/resets
- UDC driver
- VBUS sensing
- regulator/power
- configfs/libcomposite
- HID descriptors
- physical USB-PC routing
- host-side cable/port

Record negative results.

Do not silently alter assumptions just to produce a passing test.

## Resource usage

Heavy builds belong on the Build VM.

Preserve incremental build state and use reasonable parallelism based on
the VM resources.

The bridge machine should remain responsive for UART and HIL work.

## Completion rule

Do not report M5 complete based only on compilation or target-side UDC
registration.

M5 requires real hardware evidence from both sides of the USB cable.

After each meaningful slice:

1. run local tests;
2. run real HIL tests;
3. archive evidence;
4. update research documentation;
5. commit only after the pass criteria are genuinely met.
