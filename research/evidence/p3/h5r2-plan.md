# H5R2 prospective harness from the proven P3-S0 boot

P3-S0 independently passes; preparation boot ID
`1c8365c7-90bf-46fb-8db4-5ec06a745a6a` is frozen for all no-reboot H5R2 preflights.
H5R1 FAILED remains immutable. No product or target production files change.

Fresh namespace `/var/lib/blikvm-p3-h5r2`, locked account `p3-browser-h5r2`.
The H5R1 netns Python/Node implementations and H3 permission worker are copied
byte-for-byte. Their environment-variable ABI is retained. Namespace references
in launchers change; launch options, Chromium flags and browser stage protocols
do not. Every runtime file and Node/Xvfb executable is compared with H5R1 before
inheritance. A mismatch fails before browser use; a changed runtime requires a
separately frozen full three-minimal gate, never an automatic waiver.

Sequence: prepare, netns self-test, one target-free about:blank launch, sealed
archive and independent minimal/inheritance replay; then functional preparation,
read-only attached-state inventory, functional-001/002/003 with independent
replay between runs and no reboot. The gate validates physical SD/P2 identity,
all 10,690 hashes, the same boot/service generations, exact LUN attributes,
API connected=true, and full direct-read host G4 image/RO identity. Existing
inventory error gates remain. No automatic attach, eject, restart or repair.

The unchanged full MSD/HID browser contracts retain trusted HTTPS, enrolled
login, real Chromium, changing 1080p video, all UI stages, neutral HID cleanup,
media hash/write protection and permission sealing. Post-run attached-state
checks are mandatory. Any failure latches the new namespace and stops work.

Only independent acceptance of all three full preflights unlocks P3-A attempt
02: immediate inventory, accepted_cycles=0, cycle 1/12 with its own reboot.
Every cycle must add attached MSD to its postboot startup gate before Chromium.
P3-S0 is never counted. P3-B/C remain blocked. P2 PASSED, P3 UNACCEPTED,
M6/ATX and RO/overlay DEFERRED; H3 root cause UNASSIGNED, H5/H5R1 FAILED.

Local validation: false-prerequisite rejection tests (13 cases plus attached
baseline), Python compilation and Node syntax checks pass. H5R2 hardware runs
are not yet started; prospective source publication is pending authorization.
