# M8-F2 logging-only candidate

`build.py` overlays the hash-pinned public M8-E rootfs, changing only the active nginx logging directives and adding the journald drop-in. All other tar payloads and metadata must match. `cpio.sh` runs inside the existing pinned Build VM container and applies the baseline epoch normalization. No package install, kernel rebuild or application patch occurs.

Build twice into new `out/m8f2/build1` and `build2` directories, then run `finalize.py` and `check-cpio.py`. Preserve previous outputs before a new attempt. Finalize requires both archive formats to match; it reuses the accepted production candidate-2 kernel/DTB and the existing private M8-C enrollment, kept outside Git. `check-cpio.py` independently verifies every existing cpio entry's metadata and resolved hardlink content against public M8-E.

Commands from repository root:

```sh
python3 build/logging/build.py --output out/m8f2/build1
python3 build/logging/build.py --output out/m8f2/build2
# For each N=1 and N=2, using the verified pinned builder:
sudo -n docker run --rm \
  -v "$PWD/out/m8f2/build1:/candidate" \
  -v "$PWD/build/logging/cpio.sh:/build-cpio.sh:ro" \
  blikvm-ubuntu-builder:20260906 bash /build-cpio.sh
# Repeat the container command with build2.
python3 build/logging/finalize.py
python3 build/logging/check-cpio.py
python3 -m unittest discover -s tests -p test_logging_policy.py
```

The drop-in sorts after Ubuntu's `syslog.conf`; an executable test checks actual systemd precedence. Existing empty packaged nginx log files are retained for inherited inventory compatibility, but no nginx process may hold them open and they must remain empty.

The targeted controller is `lab/logging-retention.py`; it accepts only 7200 seconds and no release restart. It retains the existing strict video/browser/HID/MSD workers, audits effective logging before and after, samples minute-level retained usage, and adds the fixed documented logging/session load. Runtime evidence alone determines the logging outcome. This builder does not tag, release, start P1 or launch a full soak.
