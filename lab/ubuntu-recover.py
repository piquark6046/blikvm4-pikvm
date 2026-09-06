#!/usr/bin/env python3
"""Capture an operator-initiated target reboot and stop vendor autoboot.

No power control, target command, flash or persistent environment write.
"""
import argparse
import json
import errno
import select
from pathlib import Path
import re
import runpy
import time

lab = runpy.run_path(str(Path(__file__).with_name('labctl')))
parser = argparse.ArgumentParser()
parser.add_argument('--out-root', type=Path, required=True)
parser.add_argument('--timeout', type=float, default=900)
args = parser.parse_args()
r = lab['RunRecorder']('m7-operator-reboot-capture', args.out_root)
result = {'result': 'failed', 'clean_software_reboot_gate': False}
deadline = time.monotonic() + args.timeout
print('M7_OPERATOR_REBOOT_CAPTURE_ARMED', flush=True)
try:
    while time.monotonic() < deadline and result['result'] != 'passed':
        try:
            with lab['SerialConsole'](Path('/dev/serial/by-id/usb-1a86_USB_Serial-if00-port0'), r) as c:
                events = select.poll()
                events.register(c.fd, select.POLLHUP | select.POLLERR | select.POLLNVAL)
                text = ''
                interrupted = False
                while time.monotonic() < deadline:
                    if events.poll(0):
                        raise OSError(errno.ENODEV, 'UART disconnected; reopen stable path')
                    text += lab['clean_console'](c.read_chunk(.2))
                    if not interrupted and ('Autoboot in' in text or 'Hit any key to stop autoboot' in text):
                        c.write(b'  ')
                        interrupted = True
                    if interrupted and re.search(r'(?:^|\n)=>\s*$', text):
                        result.update(result='passed', vendor_uboot_prompt=True)
                        break
                r.save_text('recovery-console.log', text)
        except OSError as error:
            if error.errno not in (errno.ENOENT, errno.ENODEV, errno.EIO):
                raise
            result['uart_reopens'] = result.get('uart_reopens', 0) + 1
            time.sleep(.2)
except Exception as error:
    result['error'] = str(error)
print(json.dumps(r.finish(result)), flush=True)
raise SystemExit(0 if result['result'] == 'passed' else 1)
