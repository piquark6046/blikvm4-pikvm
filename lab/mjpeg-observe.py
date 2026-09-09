#!/usr/bin/env python3
"""M8-F0 observation only. Never emits a qualification pass or repairs a JPEG.

Transport commands emit HTTP headers plus curl-decoded entity bytes. Frame bodies
are delimited independently by the advertised multipart boundary, then checked
against Content-Length. A disagreement is evidence, never silently resynchronized.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import select
import subprocess
import threading
import time


def markers(data):
    def positions(marker):
        return [m.start() for m in re.finditer(re.escape(marker), data)]
    eoi = positions(b'\xff\xd9')
    end = eoi[-1]+2 if eoi else None
    tail = data[end:] if end is not None else None
    return dict(actual_length=len(data), soi_offsets=positions(b'\xff\xd8'),
                eoi_offsets=eoi, final_eoi_offset=eoi[-1] if eoi else None,
                trailing_length=len(tail) if tail is not None else None,
                trailing_hex=tail.hex() if tail is not None else None,
                tail_all_zero=not any(tail) if tail is not None else None,
                first64_hex=data[:64].hex(), last64_hex=data[-64:].hex(),
                sha256=hashlib.sha256(data).hexdigest(),
                strict_jpeg_markers=data.startswith(b'\xff\xd8') and data.endswith(b'\xff\xd9'))


class Multipart:
    def __init__(self):
        self.buffer = bytearray()
        self.boundary = None
        self.part = None

    def feed(self, data):
        self.buffer.extend(data)
        if len(self.buffer) > 16*1024*1024:
            raise ValueError('multipart buffer limit exceeded')
        if self.boundary is None:
            end = self.buffer.find(b'\r\n\r\n')
            if end < 0:
                return []
            header = bytes(self.buffer[:end])
            if not header.startswith((b'HTTP/1.0 200 ', b'HTTP/1.1 200 ')):
                raise ValueError('HTTP response not 200')
            match = re.search(rb'content-type:\s*multipart/x-mixed-replace;\s*boundary=(?:"([^"\r\n]+)"|([^;\s]+))', header, re.I)
            if not match:
                raise ValueError('missing multipart boundary')
            self.boundary = b'--'+(match[1] or match[2])
            del self.buffer[:end+4]
        rows = []
        while True:
            if self.part is None:
                end = self.buffer.find(b'\r\n\r\n')
                if end < 0:
                    break
                header = bytes(self.buffer[:end])
                lines = header.split(b'\r\n')
                if lines[0] != self.boundary:
                    raise ValueError('incorrect multipart boundary')
                fields = {}
                for line in lines[1:]:
                    key, value = line.split(b':', 1)
                    key = key.lower().decode('ascii')
                    if key in fields:
                        raise ValueError('duplicate part header')
                    fields[key] = value.strip().decode('ascii')
                length = int(fields['content-length'])
                if not 4 <= length <= 8*1024*1024 or fields.get('content-type') != 'image/jpeg':
                    raise ValueError('invalid part length/type')
                self.part = dict(content_length=length, headers=fields, part_headers_hex=header.hex())
                del self.buffer[:end+4]
            separator = b'\r\n'+self.boundary+b'\r\n'
            end = self.buffer.find(separator)
            if end < 0:
                break
            body = bytes(self.buffer[:end])
            row = dict(self.part, **markers(body), next_boundary_hex=separator.hex())
            row['length_matches'] = len(body) == self.part['content_length']
            row['anomaly'] = not row['strict_jpeg_markers'] or not row['length_matches']
            rows.append((row, body))
            del self.buffer[:end+2]  # Retain the next boundary for header validation.
            self.part = None
        return rows


def dump(path, value):
    path.write_text(json.dumps(value, indent=2)+'\n')


def observe(source, command, root, seconds, context_command, stop_file=None):
    root.mkdir(exist_ok=False)
    parser = Multipart()
    previous = pending = None
    count = anomalies = 0
    start = last = time.monotonic()
    window = rate_window = start
    hashes = set()
    rate_count = 0
    violations = []
    process = None
    context_paths = []
    context_condition = threading.Condition()
    context_done = False
    def context(path):
        requested = time.time()
        try:
            p = subprocess.run(context_command, capture_output=True, timeout=20)
            value = dict(requested_at=requested, sampled_at=time.time(), rc=p.returncode,
                         stdout=p.stdout.decode(errors='replace'), stderr=p.stderr.decode(errors='replace'))
        except Exception as ex:
            value = dict(requested_at=requested, sampled_at=time.time(), error=str(ex))
        for target in path:
            dump(target, value)
    def context_worker():
        # Coalesce an anomaly burst into timestamped shared snapshots instead
        # of starting an unbounded number of SSH processes on the bridge.
        while True:
            with context_condition:
                context_condition.wait_for(lambda: context_paths or context_done)
                if not context_paths:
                    return
                paths = context_paths[:]
                context_paths.clear()
            context(paths)
    context_thread = threading.Thread(target=context_worker)
    context_thread.start()
    try:
        with (root/'transport.stderr').open('wb') as err, (root/'frames.jsonl').open('w') as log:
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=err)
            while time.monotonic()-start < seconds:
                if stop_file and stop_file.exists():
                    break
                now = time.monotonic()
                if now-last > 3:
                    raise ValueError('continuity gap exceeds 3 seconds')
                if not select.select([process.stdout], [], [], .2)[0]:
                    continue
                data = os.read(process.stdout.fileno(), 65536)
                if not data:
                    raise ValueError('premature HTTP EOF')
                for row, body in parser.feed(data):
                    now = time.monotonic()
                    row.update(index=count, source_path=source, timestamp_utc=time.time(),
                               monotonic=now, gap=now-last,
                               lifecycle_window={'state':'steady','planned':False,'event':None})
                    last = now
                    if pending is not None:
                        dump(pending/'next.json', row)
                        pending = None
                    if row['anomaly']:
                        anomalies += 1
                        pending = root/f'anomaly-{count:09d}'
                        pending.mkdir()
                        (pending/'payload.jpg').write_bytes(body)
                        dump(pending/'metadata.json', row)
                        dump(pending/'previous.json', previous)
                        with context_condition:
                            context_paths.append(pending/'runtime.json')
                            context_condition.notify()
                    log.write(json.dumps(row)+'\n')
                    log.flush()
                    count += 1; rate_count += 1; hashes.add(row['sha256']); previous = row
                    if now-window >= 5:
                        if len(hashes) < 2:
                            violations.append({'gate':'motion_5s','start':window,'end':now})
                        window = now; hashes = set()
                    if now-rate_window >= 120:
                        fps = rate_count/(now-rate_window)
                        if fps < 27:
                            violations.append({'gate':'fps_120s','fps':fps,'start':rate_window,'end':now})
                        rate_window = now; rate_count = 0
        status = 'observation_complete'
    except Exception as ex:
        status = 'observation_incomplete'
        violations.append({'error':str(ex)})
        (root/'unparsed.bin').write_bytes(parser.buffer)
    finally:
        if process:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill(); process.wait()
            process.stdout.close()
        with context_condition:
            context_done = True
            context_condition.notify()
        context_thread.join()
        if pending:
            dump(pending/'next.json', {'unavailable':'observation ended before next complete frame'})
        dump(root/'result.json', dict(result=status, qualification='NOT_RUN', source=source,
             frames=count, anomalies=anomalies, gate_violations=violations,
             stop_reason='requested' if stop_file and stop_file.exists() else 'deadline_or_failure',
             start=start, end=time.monotonic(), seconds_requested=seconds))


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--config', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--seconds', type=float, default=900)
    p.add_argument('--stop-file', type=Path)
    a = p.parse_args()
    config = json.loads(a.config.read_text())
    a.output.mkdir(exist_ok=False)
    threads = []
    for name, source in config['sources'].items():
        thread = threading.Thread(target=observe, args=(source['path'], source['command'],
                                  a.output/name, a.seconds, config['context_command'], a.stop_file))
        thread.start(); threads.append(thread)
    for thread in threads:
        thread.join()


if __name__ == '__main__':
    main()
