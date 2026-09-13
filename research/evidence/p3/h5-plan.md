# P3-H5 prospective bridge Chromium substrate qualification

Declared before H5 preparation or browser launch, 2026-09-13.

H3 root cause: UNASSIGNED

H3 remains FAILED with zero credit. Retain SIGTRAP at chrome+0x633662b,
Chromium SHA-256 481fea1516a1f2b76454664272f12cd9dd1f20117b21e1f1498e08bc7f872c00,
ELF build ID 3693ce542c8bad6e9045e9f05df6241a3ec45cd4, private Crashpad archive,
DISPROVEN SUID-stripping hypothesis (b800439), and the separate sandbox-enabled
AppArmor failure. eadd900 retains incomplete historical contracts. No exact
successful historical Chromium argv/environment exists. Earlier attempt-02
preflight is a HISTORICAL FUNCTIONAL REFERENCE only. H4/H4b contacted neither
target nor reproduction browser. Unknown historical environments will not be
reconstructed as an H5 gate. These conclusions do not assign H3 causality.

Create /var/lib/blikvm-p3-h5 and locked nologin p3-browser-h5, no supplementary
groups, home /var/lib/blikvm-p3-h5/home. Preserve H3/legacy namespaces and all
FAILED latches. Root-only controller/sealed, root-owned read-only input,
controller-owned active parent, one browser-owned nonce leaf. Atomically rename
completed leaves under sealed without descendant permission migration.

Before launch pin executable versions/hashes, complete Chromium and Playwright
tree metadata (relative paths, hashes, ownership, modes, links, xattrs including
capabilities), clean public-CA-only NSS database, account and ancestor metadata.
Copy the runtime preserving modes; never generically chmod Chromium. Browser
write permission is limited to its active leaf and fresh approved home/cache,
with ordinary bridge /tmp used by Playwright/Xvfb as explicitly requested.

Use HOME equal to account home; omit TMPDIR and XDG_RUNTIME_DIR. Clear inherited
environment. xvfb-run -a -s '-screen 0 1600x1200x24 -nolisten tcp';
DEBUG=pw:browser*. chromium.launch({headless:false}) unchanged, no manually added
sandbox flags. Capture environment, identity, cwd, all runtime identities and
generated argv from inside every launch process before launch. Preserve raw
debug privately. Stable generated flags must match across launches; only
temporary profile/socket names may vary.

Run minimal-001, minimal-002, minimal-003 independently with fresh state and
the same HOME/contract, externally isolated network namespace with only loopback.
Launch, context, page, about:blank, clean close; no target contact. Require an
actual-UID global permission gate immediately before each launch, no SIGTRAP,
no remaining browser processes, unchanged protected inputs, complete archive,
atomic sealing and denied mutations of prior sealed runs. Any failure stops H5
without retry or target contact and earns no P3 credit.

Only after all minimal probes pass, verify continuity against accepted P2:
same physical card, all 10,690 production/enrollment hashes, UUID/PARTUUID,
machine/SSH identity, expected boot/service generations, no filesystem errors.
Then functional-001/002/003 without reboot, retaining unchanged trusted HTTPS,
enrolled login, actual Chromium UI, changing 1920x1080 video, MSD/HID browser
stages, neutral HID cleanup and exact RO-media gates. Every launch gets the
same provenance/permission gates. Every completed run is archived, hashed and
atomically sealed. Attempt mutation of functional-001 before -002, and both
prior leaves before -003; all must fail. Verify protected inputs, target files
and service generations after each run.

H5 acceptance requires all six runs and independent Build VM archive replay.
Only a bridge-harness acceptance checkpoint is permitted, no product/baseline
tag. H5 prospectively qualifies the replacement browser harness; it does not
explain H3. After independent acceptance collect a fresh target start inventory,
then start P3-A attempt 02 at accepted_cycles=0 using the frozen 12-cycle matrix.
No reflash if continuity holds. All preflights/diagnostics earn zero reboot
credit. P3-B/C blocked until P3-A 12/12 and independent review. P2 PASSED,
P3 UNACCEPTED, M6/ATX and RO/overlay DEFERRED.
