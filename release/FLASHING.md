# Verify and flash a BliKVM v4 image

This image targets the BliKVM v4 Allwinner H616 only. Check the release notes
for the exact qualification status: P3 stability, ATX, and final RO/overlay
support are not claimed by the current repository baseline.

```sh
sha256sum -c SHA256SUMS
zstd -d blikvm-v4-pikvm-<version>.img.zst -o blikvm-v4-pikvm-<version>.img
```

Enroll your own web credential, TLS identity, and network policy with
`ENROLLMENT.md` before using the image. Check the enrolled output against its
private receipt. Positively identify an **expendable** SD card using
`lsblk -o NAME,SIZE,MODEL,SERIAL,TRAN,MOUNTPOINTS` and
`ls -l /dev/disk/by-id/`; verify its size and parent device, and ensure none of
its partitions are mounted or used as swap. Never infer the destination from a
`/dev/sdX` letter or a script's automatic selection.

After independently setting `SD_BY_ID` to the verified whole-card by-id path,
and only when you intend to erase that card:

```sh
test -b "$SD_BY_ID"
sudo dd if=/private/blikvm-v4-pikvm-my-device.img of="$SD_BY_ID" \
  bs=4M iflag=fullblock oflag=direct conv=fsync status=progress
sync
```

This destroys the destination card's contents. Preserve the known-good vendor
recovery SD separately. No release workflow flashes media or changes the
target's persistent U-Boot environment.
