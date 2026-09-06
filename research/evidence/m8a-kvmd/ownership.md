# M8-A source inspection (2026-09-06)

Pin: https://github.com/pikvm/kvmd/tree/387846d22fa807f97de09750c32c1c9b26d36c1c
Tag v4.213; live refs archived in upstream-tags.txt. Archive URL is the fixed
codeload commit URL in build/kvmd/versions.env. SHA-256:
669a21aafd7e08ca85d02a965a8f3f76b3ba63ac8539ece385b1f676bdf7fdf7.
PKGBUILD and setup.py alongside this file are unmodified dependency evidence.

The pinned kvmd/apps/kvmd/streamer/runner.py starts the command via
aioproc.run_process, owns its process task, restarts failed children, and kills
the child during cleanup. streamer/__init__.py queries /state only when
runner.is_running() is true. There is no supported external-owner switch.
An inert placeholder command would misrepresent ownership and is not used.

Decision: kvmd owns/spawns the exact M7.5 uStreamer binary. The standalone unit
is stopped, disabled and masked before kvmd starts. Its packaged unit remains
available for recovery; the video udev activation request is redirected to
kvmd. The unit also declares Conflicts=ustreamer.service. Runtime directories
are owned by dedicated kvmd with the frozen ustreamer device group. No new sudo
policy is installed. The M7 lab user's existing qualification privileges are
inherited, not granted to kvmd.

Frozen command controls: /dev/kvmd-video, MJPEG 1920x1080, device-fps=30,
desired-fps=30, quality=0, encoder=HW, Unix 0660 socket at
/run/kvmd/ustreamer/ustreamer.sock. Added upstream lifecycle arguments only:
exit-on-parent-death, notify-parent, no-log-colors. RuntimeDirectory cleanup
removes sockets; KillMode=mixed lets kvmd clean up its child first, with bounded
systemd cgroup kill fallback. Hardware qualification must verify actual results.

Actual upstream API: GET /streamer; GET /streamer/snapshot (save/load/preview
options); DELETE /streamer/snapshot; GET /ws (stream=true) with streamer and
clients events and ping/pong; POST /streamer/reset and /streamer/set_params.
There is no kvmd multipart /stream route. The M8-A tests exercise snapshots and
state through kvmd, while the retained sustained multipart gate tests the owned
uStreamer socket. No nginx/proxy or invented video endpoint is added.

The downstream video-only.patch omits excluded components from daemon startup
and route registration, preserves the upstream streamer manager/runner and
snapshot implementation, and defers the unused native memsink import. It
exposes neither hardware-control routes nor network listeners. BliKVM system
metadata replaces the hardcoded Raspberry Pi platform label. This is a scoped
package variant, not an unmodified upstream full PiKVM installation.

RAM transport: the Python runtime adds packages beyond M7.5's near-full 64 MiB
compressed-image limit. M8-A uses a separate boot runner with a 96 MiB bound
at the same 0x4ff00000 load address; exclusive end 0x55f00000 is inside the
verified 0x40000000..0x80000000 1 GiB DRAM bank and below relocated U-Boot.
Image and DTB addresses remain 0x40080000 and 0x4fa00000. The earlier boot
runner and its accepted 64 MiB gate remain unchanged. This expanded RAM-only
window requires a fresh monitored boot before further qualification; it does
not authorize persistent environment or recovery media changes.
