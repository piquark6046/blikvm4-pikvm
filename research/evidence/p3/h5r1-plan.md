# P3-H5R1 prospective Chromium substrate

Declared before bridge deployment. H5 remains permanently FAILED at
`aebd3c7173d4edfbfeb10d478c8fd89963009e3b`, zero P3 credit. H3 root cause
remains UNASSIGNED. The H5 inherited-sysfs instrumentation mistake explains
only H5's prelaunch stop, not H3. Historical sources and failed namespaces
remain immutable. No AppArmor or Chromium sandbox-flag changes.

## Source and identity gate

Run the complete VM suite plus the real privileged network-namespace
regression, scan public sources for private material, commit and push clean
source to origin/main before uploading. Export exact committed source bytes,
record commit/origin-main equality and SHA-256 per deployed file. Preparation
and each run verify these bytes. Deploy only to a fresh source directory.

Create /var/lib/blikvm-p3-h5r1 and locked nologin p3-browser-h5r1 with its own
primary group and no supplemental groups. Dedicated home under home/;
controller and sealed are root 0700, input root-owned read-only, active root
0711. One nonce active leaf is browser-owned. The browser can write its
current leaf and declared HOME/profile state; ordinary /tmp remains required
by the unchanged Xvfb/Playwright contract. All H2/H3/H5 histories and exports
are protected. Every launch has an actual-UID global audit. Every prior
sealed leaf is explicitly traversed and mutation-tested; all attempts deny.

Copy the same frozen trusted H3 runtime used by H5 with metadata preserved;
compare complete runtime manifest and Chromium/Playwright pins with H5.
Prepare a fresh NSS database containing only the enrolled public CA, no
private keys. Pin Node, Playwright, Chromium, runtime manifest, NSS tools,
xvfb-run/Xvfb, account, groups, environment, cwd and Xvfb arguments before
launch. HOME is freshly populated per run and moved into the sealed leaf.
TMPDIR and XDG_RUNTIME_DIR remain absent. Environment is cleared, with
DEBUG=pw:browser*. Use exactly:

    xvfb-run -a -s '-screen 0 1600x1200x24 -nolisten tcp'
    chromium.launch({headless:false})

## Authoritative namespace gate

Never use /sys/class/net for pass/fail. Its contents or read error are only
sysfs_interfaces_observed. The controller captures host netns from itself
before /usr/bin/unshare --net, passes that identity to the isolated worker,
records /proc/self/ns/net, brings lo up, records raw ip -j link/addr/route
(including all tables and IPv6), and requires only loopback addresses/routes.
ip route get 192.168.88.2 must fail with Network is unreachable; this is a
local routing lookup, not target contact. Reject inherited socket descriptors.

After exact browser UID/GID/group drop, Node records /proc/self/ns/net,
os.networkInterfaces(), /usr/sbin/ip -j link show and routes. Namespace IDs
must match across privilege drop and differ from host. Only lo, loopback
addresses and no external routes are allowed. Record socket descriptors
and require none before launch. Sysfs diagnostics cannot affect this result.

The first live execution is netns-selftest, using this exact mechanism and
identity, with no Playwright, Chromium, Xvfb or target contact. Failure latches
H5R1 FAILED and stops. The VM regression also runs a real unshare --net with
inherited sysfs and a UID drop; host sysfs contents are intentionally not
required to have a particular value. Fixtures prove changing/removing sysfs
diagnostics does not change either validator's decisions.

## Minimal sequence and replay

After the self-test passes, minimal-001 launches Chromium, creates context
and page, navigates only about:blank, closes context and browser. Serialize
the complete prospective launch contract before launch, preserve raw
DEBUG=pw:browser* output and generated argv. Require clean exit, no SIGTRAP,
no remaining UID processes, unchanged protected inputs/history, archive hash
verification, atomic rename of the entire leaf under sealed/, and denied
post-seal mutation. Failure stops without retry, preserving contract/argv
whenever their execution points were reached.

Independently replay the archive on the Build VM without executing archived
code. Only a root-owned replay acknowledgment tied to the leaf archive hash
unlocks the next run. Repeat for minimal-002 and minimal-003 with fresh HOME
and leaf. Compare runtime identities, generated flags, UID/GID, environment,
cwd and Xvfb contract; classify only nonce leaf/HOME-profile, X display,
Xauthority and temporary Playwright paths as ephemeral. All runs earn zero
P3 reboot-cycle credit.

## Conditional functional and P3 progression

Only after all three minimal replays accept: use normal bridge networking,
collect fresh target continuity inventory before other target interaction,
and require accepted P2 physical SD, all 10,690 production/enrollment hashes,
UUID/PARTUUID, machine and SSH identities, filesystem health, and no
qualification-relevant changes. No target repair, reflash or reboot here.

Then functional-001/002/003, each independently replayed before proceeding:
trusted HTTPS and enrolled login in actual Chromium UI, changing 1920x1080
video, full frozen MSD and HID browser contracts including neutral cleanup,
exact read-only media checks, prospective launch contracts/generated argv
and global permission audits for every launch. Fresh active leaf and HOME
per run; archive/hash/atomic-seal, denied mutation, protected-state comparison
and process cleanup after each. Before functional-002 explicitly attempt
mutation of sealed functional-001; before -003 attempt both predecessors.
Every attempt must deny. Implement/deploy any functional adaptation only
from a separately tested pushed clean commit before its first execution;
it must retain the qualified runtime and launch properties.

Acceptance requires self-test, three minimal and three functional passes,
all prospective contracts/argv, isolation, independent archive replay and
unchanged target state. Commit a BRIDGE-HARNESS checkpoint only, no product
or baseline tag: H3 root cause remains UNASSIGNED; H5 remains FAILED;
H5R1 prospectively qualifies the browser harness.

Only after acceptance collect immediate fresh target inventory. If P2
continuity matches, no SD reflash. P3-A attempt 02 starts at accepted_cycles=0
and runs the frozen 12-cycle network matrix unchanged. H5/H5R1 earn zero
credit. P3-B requires 12/12 plus independent replay; P3-C requires its declared
prerequisite. P2 PASSED; P3 UNACCEPTED; M6/ATX and RO/overlay DEFERRED.
