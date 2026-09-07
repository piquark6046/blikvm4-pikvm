#!/usr/bin/env python3
"""Bounded client-side multipart/JPEG qualification over an authenticated SSH pipe.

Uses target curl solely as the Unix-socket transport; all frame parsing and
hashing happen on the bridge. A stalled connection or frozen interval fails.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import select
import subprocess
import time


class Frames:
    def __init__(self):
        self.buffer = bytearray()
        self.headers = None
        self.length = None
        self.invalid_frame = None

    def feed(self, data):
        self.buffer.extend(data)
        if len(self.buffer) > 16 * 1024 * 1024:
            raise ValueError('oversized multipart buffer')
        if self.headers is None:
            end = self.buffer.find(b'\r\n\r\n')
            if end < 0:
                return []
            self.headers = bytes(self.buffer[:end])
            del self.buffer[:end+4]
            if not self.headers.startswith((b'HTTP/1.0 200 ', b'HTTP/1.1 200 ')) or b'multipart/x-mixed-replace' not in self.headers.lower():
                raise ValueError('HTTP stream connection failed')
        frames = []
        while True:
            if self.length is None:
                end = self.buffer.find(b'\r\n\r\n')
                if end < 0:
                    break
                headers = bytes(self.buffer[:end]).lower().split(b'\r\n')
                lengths = [x.split(b':', 1)[1].strip() for x in headers if x.startswith(b'content-length:')]
                if len(lengths) != 1 or b'content-type: image/jpeg' not in headers:
                    raise ValueError('invalid JPEG part headers')
                self.length = int(lengths[0])
                if not 4 <= self.length <= 8 * 1024 * 1024:
                    raise ValueError('empty or oversized JPEG')
                del self.buffer[:end+4]
            if len(self.buffer) < self.length:
                break
            frame = bytes(self.buffer[:self.length])
            del self.buffer[:self.length]
            self.length = None
            if not frame.startswith(b'\xff\xd8') or not frame.endswith(b'\xff\xd9'):
                self.invalid_frame = frame
                raise ValueError('invalid JPEG markers')
            frames.append(frame)
        return frames


def qualify(command, seconds, output, max_gap=3):
    output.mkdir(parents=True, exist_ok=False)
    start = time.monotonic()
    result = dict(result='failed', command=command, seconds_requested=seconds)
    parser = Frames()
    records = []
    process = None
    try:
        with (output / 'transport.stderr').open('wb') as errors, (output / 'frames.jsonl').open('w') as log:
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=errors)
            last = start
            while time.monotonic() - start < seconds:
                now = time.monotonic()
                if now - last > max_gap:
                    raise RuntimeError('stream stalled beyond allowed gap')
                if not select.select([process.stdout], [], [], .2)[0]:
                    continue
                data = os.read(process.stdout.fileno(), 65536)
                if not data:
                    raise RuntimeError('stream ended before bounded interval')
                for frame in parser.feed(data):
                    last = time.monotonic()
                    record = dict(t=round(last-start, 6), bytes=len(frame), sha256=hashlib.sha256(frame).hexdigest())
                    log.write(json.dumps(record)+'\n')
                    records.append(record)
            if len(records) < seconds * 5:
                raise RuntimeError('too few frames: require at least 5 per second overall')
            # Require motion in every complete five-second window, not just at startup.
            for window in range(int(seconds // 5)):
                hashes = {r['sha256'] for r in records if window*5 <= r['t'] < (window+1)*5}
                if len(hashes) < 2:
                    raise RuntimeError(f'frozen or empty five-second window {window}')
            result['result'] = 'passed'
    except Exception as error:
        result['error'] = str(error)
        if parser.invalid_frame is not None:
            (output / 'invalid-frame.jpg').write_bytes(parser.invalid_frame)
            result['invalid_frame'] = {'bytes':len(parser.invalid_frame),'sha256':hashlib.sha256(parser.invalid_frame).hexdigest(),'first16':parser.invalid_frame[:16].hex(),'last16':parser.invalid_frame[-16:].hex()}
    finally:
        if process is not None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        result.update(elapsed=round(time.monotonic()-start, 6), frames=len(records),
                      bytes=sum(r['bytes'] for r in records), unique_hashes=len({r['sha256'] for r in records}),
                      transitions=sum(a['sha256'] != b['sha256'] for a,b in zip(records, records[1:])),
                      http_headers=(parser.headers or b'').decode(errors='replace'))
        (output / 'result.json').write_text(json.dumps(result, indent=2)+'\n')
    return result


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--seconds', type=float, default=60)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('command', nargs=argparse.REMAINDER)
    a = p.parse_args()
    if a.seconds < 5 or not a.command:
        p.error('at least 5 seconds and a transport command required')
    command = a.command[1:] if a.command[0] == '--' else a.command
    r = qualify(command, a.seconds, a.out)
    print(json.dumps(r))
    raise SystemExit(r['result'] != 'passed')
