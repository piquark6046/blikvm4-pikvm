# Development network

## Observed host state

| Role | Interface | State/address |
|---|---|---|
| Internet | `wlo1` | up, `172.15.10.116/24`, default via `172.15.10.1` |
| Proton VPN | `wg_profile` | up, `10.2.0.2/32` plus IPv6 |
| Dedicated wired lab | `enp1s0`, MAC `00:e0:4c:07:f0:0f` | administratively up but no carrier/address |
| Containers/remote route | routing includes `172.18.0.0/16` via Wi-Fi | avoid overlapping 172.16/12 lab ranges |

Firewalld is running with `wlo1` and `wg_profile` in `FedoraWorkstation`. The target's Ethernet also reports no carrier, so a direct Ethernet cable/switch connection is the remaining physical prerequisite.

## Recommended topology

```text
Internet/VPN                  isolated lab LAN
wlo1 + wg_profile            enp1s0 192.168.77.1/24
        AMD64 host  <------> BliKVM eth0 192.168.77.2/24
                              no gateway, no DNS
```

`192.168.77.0/24` does not overlap the observed Wi-Fi, VPN, or 172.18/16 route. Configure the NetworkManager connection with `ipv4.never-default yes`, no gateway/DNS, and IPv6 disabled or link-local only. This keeps TFTP/SSH working when Proton changes its default routes.

Planned host setup (not applied during research):

```bash
nmcli connection add type ethernet ifname enp1s0 con-name blikvm-lab \
  ipv4.method manual ipv4.addresses 192.168.77.1/24 \
  ipv4.never-default yes ipv6.method disabled
nmcli connection up blikvm-lab
```

Bind dnsmasq/TFTP only to `enp1s0`/`192.168.77.1`, use a dedicated TFTP root under `out/tftp`, and expose only DHCP/TFTP/SSH needed by the lab zone. Do not enable forwarding, masquerading, or a default route. Static U-Boot addresses are simpler initially; DHCP can be added after the link works.

The vendor U-Boot MAC is `02:00:eb:b5:cf:cd`, while vendor Linux displayed `12:00:eb:b5:cf:cd`. If DHCP is used, reserve both or fix the handoff later; do not assume one reservation covers both stages. TFTP filenames should include run IDs so concurrent/stale artifacts cannot be confused.

## Validation

1. Cable attached: both `enp1s0` and target report carrier.
2. Host route table has `192.168.77.0/24 dev enp1s0` and the original default/VPN routes are unchanged.
3. U-Boot can `ping 192.168.77.1` and TFTP a small hash-known file.
4. Bring-up initramfs can ping host and serve SSH at `192.168.77.2`.
5. Toggle Proton VPN; repeat steps 3-4 without changing lab configuration.

