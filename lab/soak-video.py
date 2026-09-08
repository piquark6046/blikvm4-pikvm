#!/usr/bin/env python3
"""Continuous second MJPEG client, bounded memory and explicit recovery windows.

No session secrets or response headers enter evidence. Every frame is recorded.
Only the controller's short, timestamped lifecycle window permits reconnects.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import runpy
import select
import subprocess
import time

HERE = Path(__file__).resolve().parent
H = runpy.run_path(str(HERE/'hid-api-hil.py'))
Frames = runpy.run_path(str(HERE/'stream-client.py'))['Frames']


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--private-dir', type=Path, required=True)
    a = p.parse_args()
    root = a.output
    client = H['Client'](a.private_dir)
    process = None
    secret = a.private_dir/f'soak-{os.getpid()}.conf'
    result = {'result': 'failed'}
    frames = 0
    def planned():
        return json.loads((root/'control.json').read_text())['until'] > time.monotonic()
    def connect():
        client.login()
        token = next(c.value for c in client.cookies if c.name == 'auth_token')
        fd = os.open(secret, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, 'w') as f:
            f.write('cookie = "auth_token='+token+'"\n')
        return subprocess.Popen(['curl', '--config', str(secret), '--cacert', str(a.private_dir/'ca.crt'),
                                 '--interface', '192.168.88.1', '--http1.1', '-fsS', '-N', '-i',
                                 'https://blikvm-v4.lab/streamer/stream'], stdout=subprocess.PIPE,
                                stderr=subprocess.DEVNULL)
    try:
        with (root/'frames.jsonl').open('w') as log, (root/'video-windows.jsonl').open('w') as windows:
            start = last = window = time.monotonic()
            hashes = set(); count = 0; excluded = planned(); longest = 0
            parser = Frames()
            while not (root/'stop').exists():
                now = time.monotonic()
                excluded |= planned()
                try:
                    if process is None:
                        process = connect(); parser = Frames(); last = now
                    if now-last > 3:
                        raise RuntimeError('MJPEG gap exceeds 3 seconds')
                    if select.select([process.stdout], [], [], .2)[0]:
                        data = os.read(process.stdout.fileno(), 65536)
                        if not data:
                            raise RuntimeError('MJPEG EOF')
                        for frame in parser.feed(data):
                            stamp = time.monotonic(); longest = max(longest, stamp-last); last = stamp
                            digest = hashlib.sha256(frame).hexdigest()
                            log.write(json.dumps({'t': stamp, 'bytes': len(frame), 'sha256': digest})+'\n')
                            hashes.add(digest); count += 1; frames += 1
                    if now-window >= 5:
                        row = {'start': window, 'end': now, 'frames': count, 'unique': len(hashes),
                               'max_gap': longest, 'planned': excluded}
                        windows.write(json.dumps(row)+'\n'); windows.flush(); log.flush()
                        # Motion is checked in each five-second window. 120-second throughput
                        # and continuity are replayed independently from raw frame records.
                        if not excluded:
                            assert len(hashes) >= 2 and longest <= 3, row
                        window = now; hashes = set(); count = 0; longest = 0; excluded = planned()
                        temporary = root/'video-heartbeat.json.tmp'
                        temporary.write_text(json.dumps({'t': now, 'frames': frames}))
                        temporary.replace(root/'video-heartbeat.json')
                except Exception as ex:
                    with (root/'video-events.jsonl').open('a') as events:
                        events.write(json.dumps({'t': time.monotonic(), 'error': str(ex), 'planned': planned()})+'\n')
                    if parser.invalid_frame is not None:
                        (root/f'invalid-frame-{frames}.jpg').write_bytes(parser.invalid_frame)
                        raise
                    if not planned():
                        raise
                    if process:
                        process.terminate(); process.wait(timeout=5); process = None
                    time.sleep(.5)
            result.update(result='completed_pending_replay', start=start, end=time.monotonic(), frames=frames)
    except Exception as ex:
        result['error'] = str(ex)
    finally:
        if process:
            process.terminate(); process.wait(timeout=5)
        secret.unlink(missing_ok=True)
        (root/'video-result.json').write_text(json.dumps(result, indent=2)+'\n')
    return result['result'] != 'failed'


if __name__ == '__main__':
    raise SystemExit(not main())
