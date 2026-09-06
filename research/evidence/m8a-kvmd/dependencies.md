# Explicit Ubuntu dependency map for v4.213 M8-A

Evidence: pinned PKGBUILD and setup.py in this directory, plus imports of the
patched daemon. Upstream setup.py has no install_requires. Upstream's Arch
package includes the entire appliance; its dependency list is not the minimal
daemon dependency set. Ubuntu source: signed resolute snapshot
20260906T000000Z (same as frozen M7/M7.5).

| Category | Upstream dependency | Ubuntu mapping / M8-A disposition |
|---|---|---|
| Core | Python >=3.14,<3.15 | python3 plus resolved Python 3.14 runtime |
| Core | python-yaml, python-ruamel-yaml | python3-yaml, python3-ruamel.yaml: configuration parsing/merge |
| Core | python-aiohttp, python-aiofiles | python3-aiohttp, python3-aiofiles: local server/client and async files |
| Core | python-setproctitle, python-pygments | python3-setproctitle, python3-pygments: process naming/config dump |
| Core import coupling | python-evdev | python3-evdev: shared validator/key constant tables; no input-device access |
| Video | python-pillow | python3-pil: snapshot decode/preview code imported by HTTP client |
| Video | ustreamer>=6.47 | frozen ustreamer=6.65-1blikvm2 and unchanged native libraries |
| Core service | systemd | systemd, udev inherited from M7 |
| Later HID/MSD | pyserial, serial-asyncio, spidev, hidapi, pyudev, pyusb, Xlib, libxkbcommon, zstandard | python3-serial, python3-serial-asyncio, python3-spidev, python3-hid, python3-pyudev, python3-usb, python3-xlib, libxkbcommon0, python3-zstandard; omitted |
| Later auth/web | passlib, bcrypt, pyotp, qrcode, PAM, LDAP, pyrad, nginx, certbot | python3-passlib, python3-bcrypt, python3-pyotp, python3-qrcode, python3-pam, python3-ldap, python3-pyrad, nginx, certbot; omitted |
| Optional integrations | psutil, systemd, dbus, dbus-next | python3-psutil, python3-systemd, python3-dbus, python3-dbus-next; health/log/extra managers omitted |
| Optional integrations | libgpiod, luma, pyghmi, pysmbc, paramiko, Mako, netifaces, async-lru | GPIO, OLED, IPMI, SMB, SSH plugins, nginx templates, interface discovery, auxiliary caches; omitted |
| Optional appliance/native tools | Janus, RPi access/utils, IPMI, DNS/Wi-Fi, bootconfig, NBD, OCR | no additional packages; excluded from M8-A |
| Build only | patch | Ubuntu patch; native container dpkg-deb assembles package |

No separately built ARM64 native module or wheel is needed: the HTTP path does
not use uStreamer's optional Python shared-memory binding. Native extensions
for aiohttp/evdev/Pillow/setproctitle and YAML are Ubuntu ARM64 packages, with
exact versions and transitive libraries captured in packages.tsv. Later-feature
package names are planning mappings, not verified dependency closures.

Exact full closure: [packages.tsv](packages.tsv), also enforced byte-for-byte by
`build/kvmd/packages.lock.tsv`. Build inventory: [build-packages.tsv](build-packages.tsv).
No ARM64 wheel/native component is built separately for this slice. The Debian
package is assembled reproducibly by native dpkg-deb in the pinned builder.
