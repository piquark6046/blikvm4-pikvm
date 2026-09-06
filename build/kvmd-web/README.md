# M8-B loopback web/auth derivative

M8-B is qualified; see [the acceptance record](../../research/m8b-web-auth-bringup.md).
M8-A remains frozen; M6 remains deferred. A package build or provisional boot
alone is not acceptance.

Build on the VM with `bash build/kvmd-web/build.sh package`, record/verify
`package.sha256`, then run `bash build/kvmd-web/build.sh rootfs` and
`python3 build/kvmd-web/write-manifest.py`. Each build requires a fresh staging
directory; preserve previous staging trees and logs. The inherited pinned
builder, exact M8-A rootfs hash, upstream archive hash, both downstream patch
hashes, Ubuntu snapshot and complete package inventory are checked. No pip or
npm dependencies are installed on the target.

The versioned `kvmd-web` package replaces the video-only daemon variant. It
restores upstream AuthManager, AuthApi, htpasswd plugin loading, authentication
checks and WebSocket session tracking. The upstream streamer manager/runner,
qualified uStreamer package/binary, configuration, service identity, primary
group and device rules are inherited unchanged. Root Unix-peer authentication
remains available for the existing authenticated SSH qualification clients;
the nginx worker is not a trusted Unix-peer account.

New runtime inputs are nginx/nginx-common, acl, python3-passlib, python3-pyotp
and the passlib package's required libjs-sphinxdoc dependency. OpenSSL was
already present. PAM, apache2-utils, Mako rendering, Janus services, media
services and hardware-control helpers are unnecessary. The upstream archive
contains prebuilt HTML/CSS/JS. The small web patch omits optional-app discovery
and optional Janus dependency loading from the UI.
The package omits the VNC/IPMI application pages and keeps HID/macro UI
transports disconnected; the daemon still has no hardware-control routes.

nginx uses upstream `/api/`, `/api/ws`, `/streamer/`, login and static asset
layout. It listens exclusively on `127.0.0.1:443`; no Ubuntu default site or
wildcard include is loaded. There is no plaintext HTTP listener. Upstream
`/auth/check` protects static application pages and uStreamer, while kvmd
authenticates its own API and WebSocket handshake. A failed protected page
request redirects to the public login page; protected API/video requests fail
with 401/403. Public login assets are intentionally accessible.

The nginx worker gets named ACL access only to the two runtime socket
directories. It does not join the video group. TLS permits 1.2/1.3, and nginx
adds Secure to upstream HttpOnly/SameSite=Strict session cookies.
`worker_shutdown_timeout 2s` bounds graceful termination of open MJPEG and
WebSocket connections before systemd's ten-second stop deadline.

## Private enrollment and qualification

The reproducible public package/rootfs contains no password, htpasswd database
or TLS private key. `provision.py --private-dir <ignored-private-directory>
--artifacts out/kvmd-web/artifacts` creates a random test credential, the pinned
htpasswd backend's SSHA512 encoding, an RSA-3072 self-signed certificate with
localhost/loopback identity and a Build VM SSH key. It creates a separate cpio
enrollment layer and appends it to the public RAM image without rebuilding the
public layer. It retains the bridge's existing SSH authorization. Never commit
or publish this private directory or its enrolled RAM image.

The private enrolled image is delivered only through the isolated lab's
existing RAM/TFTP boot path. Its hash is recorded separately from the
reproducible public image. Reuse the same enrollment across the bounded boot
sequence; do not inject credentials manually after each accepted boot. Recovery
remains a RAM boot of the accepted M8-A image or the untouched vendor SD.

Use the Build VM's local SSH forward `127.0.0.1:8443` to target
`127.0.0.1:443`, with a verified bridge jump and target host key captured over
UART. `lab/web-browser.mjs` runs Chromium login/logout, HTTP, WebSocket, asset,
moving-image and reload checks. A separate 120-second client measures nginx's
MJPEG endpoint with one video client, matching M8-A's rate load; Chromium stays
on the authenticated index during that measurement and checks moving video
again afterward. The gate remains >=27 delivered fps. This does not qualify
multiple simultaneous video clients.

The browser harness uses Playwright 1.58.2 / Chromium 145.0.7632.6 on the VM,
with its Ubuntu 24.04 compatibility build and the VM's font/runtime libraries.
The harness dependency lock is in `browser/`; copy its two JSON files into
`out/kvmd-web/browser/` and use `npm ci` there to reproduce the harness inputs.
`WEB_LIFECYCLE_DIR` enables explicit coordinator handshakes for independent
nginx restart, kvmd restart and HDMI off/on checks. kvmd restart discards its
upstream in-memory authentication sessions and requires browser reauthentication.
`web-video-hil.py` preserves native video/HDMI and M5 host-side regression gates;
`web-inventory.py` independently checks sockets, process identity, device
permissions, exact mode and systemd state without reading private material.

No LAN exposure, kvmd HID/MSD/ATX integration, GPIO, optional media/control
services or final read-only-root policy belongs to this slice.
