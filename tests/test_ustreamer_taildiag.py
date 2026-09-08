"""Execute the exact C instrumentation against immutable payloads, no hardware."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
DIAG = ROOT/'build/ustreamer/diagnostics'
OBSERVED = (ROOT/'tests/fixtures/m8f0/observed-trailing-data.jpg').read_bytes()
VALID = OBSERVED[:-12]


class TailDiagnosticTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.exe = Path(cls.tmp.name)/'driver'
        subprocess.run(['cc', '-std=c17', '-D_GNU_SOURCE', '-Wall', '-Wextra', '-Werror',
                        str(DIAG/'taildiag.c'), str(DIAG/'fixture-driver.c'),
                        '-pthread', '-lcrypto', '-o', str(cls.exe)], check=True)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def describe(self, data):
        with tempfile.NamedTemporaryFile() as f:
            f.write(data); f.flush()
            return json.loads(subprocess.check_output([str(self.exe), f.name]))

    def test_normal_exact_eoi(self):
        row = self.describe(VALID)
        self.assertFalse(row['suspicious'])
        self.assertTrue(row['structural_eoi_exists'])
        self.assertEqual(row['trailing_hex'], '')
        self.assertEqual(row['sha256'], row['through_final_eoi_sha256'])

    def test_preserved_run02_and_uvc_fields(self):
        row = self.describe(OBSERVED)
        self.assertEqual(row['sha256'], 'd2cd33ac727787d035aef578156fc269a7b796c25b5ff5fb5873c844cf561d3c')
        self.assertEqual(row['through_final_eoi_sha256'], hashlib.sha256(VALID).hexdigest())
        self.assertTrue(row['suspicious'])
        self.assertEqual(row['eoi_offsets'], [41434])
        self.assertEqual(row['trailing_length'], 12)
        self.assertEqual(row['trailing_hex'], '0c8fcf214aa5e06389a5d900')
        self.assertEqual(row['first64_hex'], OBSERVED[:64].hex())
        self.assertEqual(row['last64_hex'], OBSERVED[-64:].hex())
        uvc = row['uvc_candidate']
        for key, expected in dict(bHeaderLength=12, bmHeaderInfo=143, FID=1, EOF=1,
                                  PTS_present=True, SCR_present=True, PTS=2773098959,
                                  SCR_clock=2777244640, SCR_SOF=217, ERR=0, STI=0,
                                  reserved=0, EOH=1, length_matches_tail=True,
                                  fields_complete=True, header_shaped_only=True).items():
            self.assertEqual(uvc[key], expected, key)

    def test_padding_and_garbage_remain_suspicious(self):
        for tail in (bytes(12), b'garbage', b'\0', b'\xff'):
            row = self.describe(VALID+tail)
            self.assertTrue(row['suspicious'])
            self.assertEqual(row['trailing_hex'], tail.hex())
            if row['uvc_candidate']:
                self.assertFalse(row['uvc_candidate']['header_shaped_only'])

    def test_uvc_shaped_garbage_lengths_and_truncation(self):
        for tail in (b'\x02\x82', b'\x06\x84'+bytes(4), b'\x08\x88'+bytes(6),
                     b'\x0c\x8c'+bytes(10), b'\x0e\x8c'+bytes(12)):
            row = self.describe(VALID+tail)
            self.assertTrue(row['suspicious'])
            self.assertTrue(row['uvc_candidate']['header_shaped_only'])
            self.assertEqual(row['uvc_candidate']['bHeaderLength'], len(tail))
        for tail in (b'\x0c\x8f'+bytes(9), b'\x0c\x8f'+bytes(11), b'\x02\x8f'):
            row = self.describe(VALID+tail)
            self.assertTrue(row['suspicious'])
            self.assertFalse(row['uvc_candidate']['header_shaped_only'])
        row = self.describe(VALID+b'\x02\xf3')
        self.assertEqual([row['uvc_candidate'][x] for x in ('ERR','STI','reserved')], [1,1,1])

    def test_truncated_and_embedded_false_eoi(self):
        for data in (VALID[:-2], b'', b'\xff', b'\xff\xd8\xff\xe0\x00\x06\xff\xd9xxgarbage'):
            row = self.describe(data)
            self.assertFalse(row['suspicious'])
            self.assertFalse(row['structural_eoi_exists'])
        self.assertIsNone(self.describe(VALID[:-2])['through_final_eoi_sha256'])

    def test_multiple_eoi_offsets_final_controls_tail(self):
        data = VALID+b'junk\xff\xd9tail'
        row = self.describe(data)
        self.assertEqual(row['eoi_offsets'], [len(VALID)-2, len(VALID)+4])
        self.assertEqual(row['final_eoi_offset'], len(VALID)+4)
        self.assertEqual(row['trailing_hex'], b'tail'.hex())
        self.assertTrue(row['suspicious'])
        self.assertFalse(self.describe(data[:-4])['suspicious'])

    def runtime(self, mode, data=OBSERVED):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); payload=root/'input';payload.write_bytes(data)
            logs=root/'logs';logs.mkdir(mode=0o700)
            if mode=='flush': (logs/'flush.request').touch(mode=0o600)
            env=os.environ.copy();env['USTREAMER_TAILDIAG_DIR']=str(logs)
            subprocess.run([str(self.exe), str(payload), mode], env=env, check=True)
            rows={p.name:json.loads(p.read_text()) for p in logs.glob('*.json')}
            bins={p.name:p.read_bytes() for p in logs.glob('*.bin')}
            self.assertEqual(payload.read_bytes(), data)
            self.assertTrue(all(p.stat().st_mode&0o777 == 0o600 for p in logs.iterdir()))
            return rows, bins

    def test_three_boundary_correlation_and_raw_identity(self):
        rows,bins=self.runtime('once')
        self.assertEqual(len(bins),3)
        self.assertTrue(all(b==OBSERVED for b in bins.values()))
        for stage in ('dqbuf','hw_jpeg','http_exposed'):
            row=rows[f'{stage}-001.json']
            self.assertEqual(row['boundary']['v4l2']['sequence'],12345)
            self.assertEqual(row['boundary']['v4l2']['index'],7)
            self.assertEqual(row['boundary']['v4l2']['timestamp_usec'],456789)
            self.assertEqual(row['boundary']['grab_begin_time'],'123.456000')
            self.assertEqual(row['jpeg'], self.describe(OBSERVED))
        self.assertEqual(rows['http_exposed-001.json']['boundary']['encode_end_time'],'123.478901')
        self.assertEqual(len(rows['http_exposed-001.json']['prior_boundaries']),2)

    def test_copy_origin_has_normal_capture_hash(self):
        rows,_=self.runtime('copy-origin')
        self.assertNotIn('dqbuf-001.json',rows)
        prior=rows['hw_jpeg-001.json']['prior_boundaries'][0]
        self.assertFalse(prior['suspicious'])
        self.assertEqual(prior['sha256'],hashlib.sha256(VALID).hexdigest())

    def test_duplicate_capture_timestamp_is_not_false_proof(self):
        rows,_=self.runtime('ambiguous')
        row=rows['hw_jpeg-001.json']
        self.assertTrue(row['boundary']['correlation_ambiguous'])
        self.assertIsNone(row['boundary']['v4l2'])
        self.assertEqual(row['prior_boundaries'],[])
        self.assertEqual(rows['summary.json']['stages'][1]['metadata_misses'],1)

    def test_external_observer_can_flush_normal_boundary_hashes(self):
        import runpy
        rows,bins=self.runtime('flush',VALID)
        self.assertEqual(bins,{})
        boundaries=rows['recent-001.json']['boundaries']
        self.assertEqual([b['stage'] for b in boundaries],['dqbuf','hw_jpeg','http_exposed'])
        self.assertTrue(all(not b['suspicious'] for b in boundaries))
        self.assertTrue(all(b['sha256']==hashlib.sha256(VALID).hexdigest() for b in boundaries))
        self.assertEqual(rows['summary.json']['snapshots_written'],1)
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);diag=root/'diag';diag.mkdir();clients=root/'clients'
            for name,row in rows.items(): (diag/name).write_text(json.dumps(row))
            for source in ('direct','https'):
                path=clients/source;path.mkdir(parents=True)
                row=dict(index=10,sha256=hashlib.sha256(OBSERVED).hexdigest(),anomaly=True,
                         actual_length=len(OBSERVED),trailing_hex=OBSERVED[-12:].hex(),
                         headers={'x-ustreamer-grab-begin-time':'123.456000',
                                  'x-ustreamer-encode-end-time':'123.478901'})
                (path/'frames.jsonl').write_text(json.dumps(row)+'\n')
            correlate=runpy.run_path(str(ROOT/'lab/mjpeg-taildiag-correlate.py'))['correlate']
            result=correlate(diag,clients)
            self.assertEqual(len(result['recent_boundary_matches']),3)
            self.assertTrue(all(not m['payload_matches'] for r in result['recent_boundary_matches'] for m in r['multipart_matches']))

    def test_rate_limit_bounds_and_no_normal_payloads(self):
        rows,bins=self.runtime('burst')
        self.assertEqual(len(bins),3)
        for row in rows['summary.json']['stages']:
            self.assertEqual(row['accepted'],1)
            self.assertEqual(row['written'],1)
            self.assertEqual(row['suppressed'],99)
        rows,_=self.runtime('bounds')
        self.assertEqual(rows['summary.json']['stages'][0]['oversized_or_invalid_length'],2)
        rows,bins=self.runtime('once',VALID)
        self.assertEqual(bins,{})
        self.assertEqual(set(rows),{'session.json','summary.json'})

    def test_disabled_and_reused_directory_do_not_mutate(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'input';p.write_bytes(OBSERVED)
            env=os.environ.copy();env.pop('USTREAMER_TAILDIAG_DIR',None)
            subprocess.run([str(self.exe),str(p),'once'],env=env,check=True)
            env['USTREAMER_TAILDIAG_DIR']=tmp
            subprocess.run([str(self.exe),str(p),'once'],env=env,check=True)
            hashes={f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in Path(tmp).iterdir()}
            subprocess.run([str(self.exe),str(p),'once'],env=env,check=True)
            self.assertEqual(hashes,{f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in Path(tmp).iterdir()})

    def test_offline_multipart_join_and_tamper_rejection(self):
        import runpy
        correlate=runpy.run_path(str(ROOT/'lab/mjpeg-taildiag-correlate.py'))['correlate']
        rows,bins=self.runtime('once')
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);diag=root/'diag';diag.mkdir();clients=root/'clients'
            for name,row in rows.items(): (diag/name).write_text(json.dumps(row))
            for name,data in bins.items(): (diag/name).write_bytes(data)
            for source in ('direct','https'):
                path=clients/source;path.mkdir(parents=True)
                row=dict(index=10,sha256=hashlib.sha256(OBSERVED).hexdigest(),anomaly=True,
                         actual_length=len(OBSERVED),trailing_hex=OBSERVED[-12:].hex(),
                         headers={'x-ustreamer-grab-begin-time':'123.456000',
                                  'x-ustreamer-encode-end-time':'123.478901'})
                (path/'frames.jsonl').write_text(json.dumps(row)+'\n')
            result=correlate(diag,clients)
            self.assertEqual(len(result['events']),3)
            for event in result['events']:
                self.assertEqual(len(event['multipart_matches']),2)
                self.assertTrue(all(r['payload_matches'] and r['tail_matches'] for r in event['multipart_matches']))
            (diag/'dqbuf-001.bin').write_bytes(VALID)
            with self.assertRaisesRegex(ValueError,'hash/length mismatch'):
                correlate(diag,clients)
