import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('ubuntu_gate', ROOT / 'lab/ubuntu-reboot-gate.py')
GATE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GATE)


class RebootGateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.runs = self.root / 'runs'
        self.runs.mkdir()
        self.series = self.root / 'series.jsonl'
        self.reports = []
        previous = None
        for n in range(20):
            run = self.runs / str(n)
            run.mkdir()
            report = dict(run_id=str(n), result='passed', stage='ubuntu_network_ssh', finished_at=f'{n:02d}:59')
            self.reports.append(report)
            (run / 'test-results.json').write_text(json.dumps(report))
            (run / 'metadata.json').write_text(json.dumps(dict(run_id=str(n), command='boot-ubuntu',
                started_at=f'{n:02d}:00', artifacts={'Image': 'unchanged'}, target_storage_writes=False)))
            boot = f'00000000-0000-0000-0000-{n:012d}'
            (run / 'identity.log').write_text(boot + '\n')
            (run / 'uart.raw').write_text(f'bootid={previous}; systemctl reboot; reboot.target; '
                'reboot: Restarting system; U-Boot SPL 2021.10-armbian')
            previous = boot
            for name in ('journal.log', 'ip-addr.log', 'ip-route.log', 'ethtool.log', 'ping.log',
                         'ssh-authentication.log', 'lab-service-policy.log', 'dmesg.log', 'uboot.log',
                         'runner.py', 'rootfs-manifest.json', 'systemctl-status.log'):
                (run / name).write_text('fixture')
            (run / 'pid1.log').write_text('systemd\n')
            (run / 'systemctl-status.log').write_text('    State: running\n')
            (run / 'multi-user.log').write_text('active\nactive\n')
            (run / 'systemctl-failed.log').write_text('0 loaded units listed.\n')
            (run / 'sshd-effective.log').write_text('passwordauthentication no\nkbdinteractiveauthentication no\n'
                'permitrootlogin no\nauthenticationmethods publickey\n')
        self.series.write_text('\n'.join(map(json.dumps, self.reports)))

    def test_full_chain_passes_but_incomplete_series_does_not(self):
        self.assertTrue(GATE.audit(self.series, self.runs, 20)['final_20_boot_gate'])
        self.series.write_text('\n'.join(map(json.dumps, self.reports[:-1])))
        with self.assertRaises(ValueError):
            GATE.audit(self.series, self.runs, 20)

    def test_reused_boot_id_is_rejected(self):
        (self.runs / '8/identity.log').write_text((self.runs / '7/identity.log').read_text())
        with self.assertRaises(ValueError):
            GATE.audit(self.series, self.runs, 20)

    def test_missing_clean_shutdown_is_rejected(self):
        (self.runs / '8/uart.raw').write_text('U-Boot SPL 2021.10-armbian')
        with self.assertRaises(ValueError):
            GATE.audit(self.series, self.runs, 20)

    def test_early_snapshot_is_rejected_even_when_multi_user_is_active(self):
        (self.runs / '8/systemctl-status.log').write_text('    State: starting\n')
        with self.assertRaises(ValueError):
            GATE.audit(self.series, self.runs, 20)

    def test_omitted_failed_attempt_is_rejected(self):
        extra = self.runs / 'omitted'
        extra.mkdir()
        (extra / 'metadata.json').write_text(json.dumps(dict(run_id='omitted', command='boot-ubuntu',
            started_at='08:30', result='failed')))
        with self.assertRaises(ValueError):
            GATE.audit(self.series, self.runs, 20)
