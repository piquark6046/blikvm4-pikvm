#!/usr/bin/env python3
"""M7 RAM boot and userspace checks on the bridge, using the frozen UART engine."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import runpy
import shutil
import subprocess
import time

LAB = runpy.run_path(str(Path(__file__).with_name('labctl')))


def boot(args):
    recorder = LAB['RunRecorder']('boot-ubuntu', args.out_root)
    recorder.save_text('runner.py', Path(__file__).read_text())
    recorder.metadata.setdefault('automation_sha256', {})['lab/ubuntu-boot.py'] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    stage = 'preflight'
    manifest = json.loads((args.artifacts / 'manifest.json').read_text())
    result = {'result': 'failed'}
    try:
        for name in ('Image', 'sun50i-h616-blikvm-v4.dtb', 'initramfs.cpio.gz', 'linux.config'):
            p = args.artifacts / name
            expected = manifest['artifacts'][name]
            with p.open('rb') as stream:
                digest = hashlib.file_digest(stream, 'sha256').hexdigest()
            if digest != expected['sha256'] or p.stat().st_size != expected['size']:
                raise RuntimeError('artifact mismatch: ' + name)
        # Deliberately retain the existing proven 64 MiB transport limit.
        if manifest['artifacts']['initramfs.cpio.gz']['size'] >= 0x4000000:
            raise RuntimeError('Ubuntu initramfs exceeds verified 64 MiB window; qualify another transport first')
        recorder.metadata.update(artifacts=manifest['artifacts'], build_source=manifest['source'],
                                 root_transport='ram-rw', target_storage_writes=False)
        recorder.save_text('rootfs-manifest.json', json.dumps(manifest, indent=2))
        publication = args.tftp_root / 'm7' / manifest['artifacts']['initramfs.cpio.gz']['sha256'][:20]
        if not publication.exists():
            temporary = publication.with_name(publication.name + '.' + recorder.run_id)
            temporary.mkdir(parents=True)
            for name in ('Image', 'sun50i-h616-blikvm-v4.dtb', 'initramfs.cpio.gz'):
                shutil.copyfile(args.artifacts / name, temporary / name)
            temporary.rename(publication)
        for name in ('Image', 'sun50i-h616-blikvm-v4.dtb', 'initramfs.cpio.gz'):
            with (publication / name).open('rb') as stream:
                if hashlib.file_digest(stream, 'sha256').hexdigest() != manifest['artifacts'][name]['sha256']:
                    raise RuntimeError('published artifact mismatch: ' + name)
        prefix = str(publication.relative_to(args.tftp_root))
        with LAB['SerialConsole'](args.uart, recorder) as console:
            session = LAB['UBootSession'](console, recorder, password_file=args.target_password_file)
            stage = 'reboot'
            session.acquire_prompt(allow_reboot=True)
            stage = 'uboot'
            recorder.metadata['phy_workaround'] = LAB['apply_vendor_phy_workaround'](session)
            addresses = LAB['required_load_addresses'](session)
            if {k: int(v, 16) for k, v in addresses.items()} != {
                'kernel_addr_r': 0x40080000, 'ramdisk_addr_r': 0x4FF00000, 'fdt_addr_r': 0x4FA00000}:
                raise RuntimeError('unqualified U-Boot load addresses')
            stage = 'tftp'
            for command in ('setenv ipaddr 192.168.88.2', 'setenv serverip 192.168.88.1',
                            'setenv netmask 255.255.255.0'):
                session.execute(command)
            for variable, name in (('kernel_addr_r', 'Image'), ('ramdisk_addr_r', 'initramfs.cpio.gz'),
                                    ('fdt_addr_r', 'sun50i-h616-blikvm-v4.dtb')):
                transfer = session.execute(f'tftp ${{{variable}}} {prefix}/{name}', 180)
                LAB['parse_tftp_size'](transfer, manifest['artifacts'][name]['size'], name)
                if variable == 'ramdisk_addr_r':
                    session.execute('setenv ramdisk_size ${filesize}')
            session.execute('setenv bootargs "console=ttyS0,115200n8 earlycon loglevel=6 '
                            'printk.time=1 rdinit=/sbin/init net.ifnames=0 panic=-1"')
            stage = 'systemd_boot'
            console.write_line(b'booti ${kernel_addr_r} ${ramdisk_addr_r}:${ramdisk_size} ${fdt_addr_r}')
            console.wait_for((re.compile(r'blikvm@blikvm-m7:.*\$\s*$'),), 180)
            console.write_line(b'sudo -n -i')
            console.wait_for((re.compile(r'root@blikvm-m7:.*#\s*$'),), 20)
            def target(name, command, timeout=30):
                rc, output = LAB['capture_shell_command'](console, recorder, name + '.log',
                                                         name.replace('-', '_'), '(set -e; ' + command + ')', timeout)
                if rc:
                    raise RuntimeError(f'{name} exited {rc}: {output[-1000:]}')
                return output
            stage = 'multi_user'
            target('systemd-ready', 'systemctl is-system-running --wait', 120)
            target('pid1', "test \"$(cat /proc/1/comm)\" = systemd && cat /proc/1/comm")
            target('multi-user', 'systemctl is-active multi-user.target && systemctl is-active serial-getty@ttyS0.service')
            target('systemctl-failed', "systemctl --failed --no-pager; test \"$(systemctl --failed --no-legend --plain | wc -l)\" -eq 0")
            target('systemctl-status', 'systemctl status --no-pager')
            target('identity', 'hostname; cat /etc/os-release /etc/blikvm-build; uname -a; cat /proc/sys/kernel/random/boot_id')
            target('journal', 'journalctl -b --no-pager -n 160')
            stage = 'network'
            target('ip-addr', "ip -br addr; ip -o -4 addr show dev eth0; test \"$(ip -o -4 addr show dev eth0 | awk '{print $4}')\" = 192.168.88.2/24; ip link show eth0 | grep LOWER_UP")
            target('ip-route', "ip route; ip -6 route; test -z \"$(ip route show default)\"; test -z \"$(ip -6 route show default)\"")
            target('ethtool', 'ethtool eth0')
            target('ping', 'ping -c 5 -W 2 192.168.88.1')
            stage = 'ssh'
            target('ssh-service', 'systemctl is-active ssh.service')
            if args.require_lab_presets:
                target('lab-service-policy', '! systemctl is-active --quiet systemd-resolved.service && '
                       'test "$(systemctl is-enabled ssh.socket)" = disabled')
            ssh_config = target('sshd-effective', '/usr/sbin/sshd -T')
            for setting in ('passwordauthentication no', 'kbdinteractiveauthentication no',
                            'permitrootlogin no', 'authenticationmethods publickey'):
                if setting not in ssh_config.splitlines():
                    raise RuntimeError('sshd effective setting missing: ' + setting)
            # Trust host public key obtained over the already-identified UART.
            hostkey = target('ssh-host-key', 'cat /etc/ssh/ssh_host_ed25519_key.pub').strip()
            known = recorder.path / 'known_hosts'
            known.write_text('192.168.88.2 ' + hostkey + '\n')
            p = subprocess.run(['ssh', '-i', str(args.ssh_key), '-o', 'IdentitiesOnly=yes',
                                '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes',
                                '-o', 'UserKnownHostsFile=' + str(known), '-o', 'ConnectTimeout=10',
                                'blikvm@192.168.88.2',
                                'set -e; id; hostname; systemctl is-system-running; '
                                'systemctl is-active multi-user.target; cat /etc/blikvm-build'],
                               capture_output=True, text=True, timeout=30)
            recorder.save_text('ssh-authentication.log', p.stdout + p.stderr)
            if p.returncode:
                raise RuntimeError('bridge key authentication failed')
            target('dmesg', 'dmesg')
            target('udc', 'ls -l /sys/class/udc; hid-keyboard state')
            result.update(result='passed', stage='ubuntu_network_ssh',
                          hardware_regressions='pending', final_20_boot_gate=False)
    except Exception as error:
        result.update(stage=stage, error=str(error))
    return recorder.finish(result)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--artifacts', type=Path, required=True)
    parser.add_argument('--out-root', type=Path, required=True)
    parser.add_argument('--tftp-root', type=Path, default=Path('/srv/tftp'))
    parser.add_argument('--uart', type=Path, default=Path('/dev/serial/by-id/usb-1a86_USB_Serial-if00-port0'))
    parser.add_argument('--ssh-key', type=Path, default=Path('/home/user/.local/share/blikvm-m7/id_ed25519'))
    parser.add_argument('--boots', type=int, default=1)
    parser.add_argument('--target-password-file', type=Path,
                        help='Existing external vendor credential, used only if recovery SD booted')
    parser.add_argument('--require-lab-presets', action='store_true')
    args = parser.parse_args()
    if not 1 <= args.boots <= 20:
        parser.error('--boots must be 1..20')
    results = []
    for _ in range(args.boots):
        result = boot(args)
        results.append(result)
        print(json.dumps(result), flush=True)
        if result['result'] != 'passed':
            raise SystemExit(1)
