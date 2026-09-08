import pathlib
import runpy
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
M = runpy.run_path(str(ROOT/'lab/mjpeg-observe.py'))
OBSERVED = (ROOT/'tests/fixtures/m8f0/observed-trailing-data.jpg').read_bytes()
VALID = OBSERVED[:OBSERVED.rfind(b'\xff\xd9')+2]
HEADER = b'HTTP/1.0 200 OK\r\nContent-Type: multipart/x-mixed-replace;boundary=test\r\n\r\n'


def part(body, length=None):
    return b'--test\r\nContent-Type: image/jpeg\r\nContent-Length: '+str(len(body) if length is None else length).encode()+b'\r\n\r\n'+body+b'\r\n'


class ObserveTests(unittest.TestCase):
    def parse(self, bodies, chunk):
        wire = HEADER+b''.join(part(b) for b in bodies)+b'--test\r\n'
        parser = M['Multipart'](); rows = []
        for i in range(0, len(wire), chunk):
            rows.extend(parser.feed(wire[i:i+chunk]))
        return rows

    def test_exact_valid_and_observed_and_garbage_and_truncated(self):
        bodies = [VALID, OBSERVED, VALID+b'garbage', VALID[:-2], VALID+b'\0'*12]
        rows = self.parse(bodies, 65536)
        self.assertEqual([row['anomaly'] for row, body in rows], [False, True, True, True, True])
        self.assertEqual([body for row, body in rows], bodies)
        self.assertEqual(rows[1][0]['trailing_hex'], '0c8fcf214aa5e06389a5d900')
        self.assertFalse(rows[1][0]['tail_all_zero'])
        self.assertIsNone(rows[3][0]['trailing_length'])

    def test_observation_02_nonzero_tail_ending_in_zeroes_is_not_padding(self):
        import hashlib
        payload=(ROOT/'tests/fixtures/m8f0/observation-02-trailing-data.jpg').read_bytes()
        self.assertEqual(hashlib.sha256(payload).hexdigest(),
                         '3e473fc68e67ee0439ea28760886f65259492f1e024e468c7bf10530a9953cf3')
        [(row,body)]=self.parse([payload],7)
        self.assertEqual(body,payload)
        self.assertTrue(row['anomaly'])
        self.assertTrue(row['length_matches'])
        self.assertEqual(row['trailing_hex'],'0c8eed6907f539af46f50000')
        self.assertFalse(row['tail_all_zero'])
        strict=runpy.run_path(str(ROOT/'lab/stream-client.py'))['Frames']()
        with self.assertRaisesRegex(ValueError,'invalid JPEG markers'):
            strict.feed(HEADER+part(payload)+b'--test\r\n')
        self.assertEqual(strict.invalid_frame,payload)

    def test_split_headers_body_consecutive(self):
        for chunk in (1, 2, 7, 64, 4096, 1000000):
            with self.subTest(chunk=chunk):
                rows = self.parse([VALID, OBSERVED, VALID], chunk)
                self.assertEqual([body for row, body in rows], [VALID, OBSERVED, VALID])
                self.assertTrue(all(row['length_matches'] for row, body in rows))
                self.assertEqual(rows[1][0]['next_boundary_hex'], b'\r\n--test\r\n'.hex())

    def test_length_independently_measured(self):
        parser = M['Multipart']()
        rows = parser.feed(HEADER+part(OBSERVED, len(VALID))+b'--test\r\n')
        self.assertFalse(rows[0][0]['length_matches'])
        self.assertEqual(rows[0][1], OBSERVED)

    def test_frozen_qualification_still_rejects_observed(self):
        strict = runpy.run_path(str(ROOT/'lab/stream-client.py'))['Frames']()
        with self.assertRaisesRegex(ValueError, 'invalid JPEG markers'):
            strict.feed(HEADER+part(OBSERVED)+b'--test\r\n')
        self.assertEqual(strict.invalid_frame, OBSERVED)


class CompareTests(unittest.TestCase):
    def test_correlated_payload_mismatch_and_motion_rate_failures(self):
        import json
        import tempfile
        compare = runpy.run_path(str(ROOT/'lab/mjpeg-observe-compare.py'))['replay']
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            for name in ('direct', 'https'):
                (root/name).mkdir()
                with (root/name/'frames.jsonl').open('w') as f:
                    for i in range(122):
                        row = dict(index=i, monotonic=float(i), sha256='constant',
                            content_length=10, actual_length=10, anomaly=False,
                            trailing_hex='', headers={'x-ustreamer-grab-begin-time':str(i),
                            'x-ustreamer-encode-end-time':str(i)})
                        if name == 'https' and i == 5:
                            row.update(sha256='altered', anomaly=True, trailing_hex='ff')
                        f.write(json.dumps(row)+'\n')
            result = compare(root)
            self.assertEqual(result['qualification'], 'NOT_RUN')
            self.assertEqual(result['shared_capture_keys'], 122)
            self.assertEqual(len(result['payload_mismatches']), 1)
            self.assertEqual(len(result['shared_anomalies']), 1)
            self.assertFalse(result['clients']['direct']['fps_gate_met'])
            self.assertTrue(result['clients']['direct']['motion_failure_windows'])


class ArchiveTests(unittest.TestCase):
    def test_anomaly_is_preserved_with_neighbors_and_failed_context(self):
        import json
        import sys
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            wire = root/'wire.bin'
            wire.write_bytes(HEADER+part(VALID)+part(OBSERVED)+part(VALID)+b'--test\r\n')
            command = [sys.executable,'-c',
                'import sys,time; sys.stdout.buffer.write(open(sys.argv[1],"rb").read()); sys.stdout.flush(); time.sleep(2)', str(wire)]
            output = root/'evidence'
            M['observe']('test-only',command,output,.25,[sys.executable,'-c','raise SystemExit(2)'])
            anomaly = output/'anomaly-000000001'
            self.assertEqual((anomaly/'payload.jpg').read_bytes(),OBSERVED)
            self.assertEqual(json.loads((anomaly/'previous.json').read_text())['index'],0)
            self.assertEqual(json.loads((anomaly/'next.json').read_text())['index'],2)
            self.assertEqual(json.loads((anomaly/'runtime.json').read_text())['rc'],2)
            result = json.loads((output/'result.json').read_text())
            self.assertEqual(result['anomalies'],1)
            self.assertEqual(result['qualification'],'NOT_RUN')
