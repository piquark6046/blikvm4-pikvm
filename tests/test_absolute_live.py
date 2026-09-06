from pathlib import Path
import runpy
import unittest

LIVE = runpy.run_path(str(Path(__file__).resolve().parents[1]/'lab/absolute-live.py'))

class PhysicalSequenceTests(unittest.TestCase):
    def test_final_transition_and_interval_required(self):
        log = '\n'.join([
            '2026-09-06T04:26:22,062391+00:00 usb 1-3: USB disconnect, device number 22',
            '2026-09-06T04:26:22,338462+00:00 usb 1-3: new high-speed USB device number 23 using xhci_hcd',
            '2026-09-06T04:26:22,859784+00:00 usb 1-3: USB disconnect, device number 23',
            '2026-09-06T04:26:29,808189+00:00 usb 1-3: new high-speed USB device number 24 using xhci_hcd'])
        assess=LIVE['reconnect_sequence']
        self.assertTrue(assess(log,'1-3','22','24')['passed'])
        for candidate, port, before, after in [
            (log,'1-3','22','23'), (log,'1-4','22','24'),
            (log.replace('29,808189','23,808189'),'1-3','22','24'),
            (log.rsplit('\n',1)[0],'1-3','22','24'),
            (log.replace('disconnect, device number 23','disconnect, device number 99'),'1-3','22','24')]:
            with self.assertRaises(RuntimeError): assess(candidate,port,before,after)
