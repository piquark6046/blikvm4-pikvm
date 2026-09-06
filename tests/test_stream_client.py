import runpy
from pathlib import Path
import unittest

Frames = runpy.run_path(str(Path(__file__).resolve().parents[1] / 'lab/stream-client.py'))['Frames']


class StreamClientTests(unittest.TestCase):
    def stream(self, frame=b'\xff\xd8hello\xff\xd9'):
        return (b'HTTP/1.1 200 OK\r\nContent-Type: multipart/x-mixed-replace;boundary=x\r\n\r\n'
                b'--x\r\nContent-Type: image/jpeg\r\nContent-Length: '+str(len(frame)).encode()+b'\r\n\r\n'+frame+b'\r\n--x\r\n')

    def test_arbitrary_transport_chunk_boundaries(self):
        p = Frames()
        frames = []
        for byte in self.stream():
            frames.extend(p.feed(bytes([byte])))
        self.assertEqual(frames, [b'\xff\xd8hello\xff\xd9'])

    def test_rejects_http_error_and_empty_or_corrupt_frames(self):
        for stream in (self.stream().replace(b'200 OK', b'503 Failed'), self.stream(b''), self.stream(b'garbage')):
            with self.assertRaises(ValueError):
                Frames().feed(stream)

    def test_http_10_upstream_response(self):
        self.assertEqual(len(Frames().feed(self.stream().replace(b'HTTP/1.1', b'HTTP/1.0'))), 1)

    def test_multiple_frames_in_one_read(self):
        stream = self.stream()
        part = stream.split(b'\r\n\r\n',1)[1]
        self.assertEqual(len(Frames().feed(stream + part)), 2)
