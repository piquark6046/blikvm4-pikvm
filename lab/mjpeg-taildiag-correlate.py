#!/usr/bin/env python3
"""Join diagnostic boundaries to archived multipart observations; no qualification."""
import argparse
import hashlib
import json
from pathlib import Path


def correlate(diagnostics, clients):
    events=[]
    recent=[]
    keys=set()
    for path in sorted(diagnostics.glob('*.json')):
        row=json.loads(path.read_text())
        for boundary in row.get('boundaries',[]):
            recent.append(dict(file=path.name,boundary=boundary))
            keys.add(boundary['grab_begin_time'])
        if 'boundary' not in row:
            continue
        b=row['boundary']; jpeg=row['jpeg']
        if b['sha256'] != jpeg['sha256'] or b['bytesused'] != jpeg['bytesused']:
            raise ValueError('inconsistent diagnostic metadata: '+path.name)
        if row['payload_file']:
            name=row['payload_file']
            if Path(name).name != name:
                raise ValueError('invalid diagnostic payload path')
            data=(diagnostics/name).read_bytes()
            if hashlib.sha256(data).hexdigest()!=jpeg['sha256'] or len(data)!=jpeg['bytesused']:
                raise ValueError('diagnostic raw payload hash/length mismatch')
            offset=jpeg['final_eoi_offset']
            if data[offset:offset+2] != b'\xff\xd9' or data[offset+2:].hex()!=jpeg['trailing_hex']:
                raise ValueError('diagnostic tail mismatch')
        events.append(dict(file=path.name, **row))
        keys.add(b['grab_begin_time'])
    matches={}
    unmatched_anomalies=0
    # Keep only keys near diagnostic anomalies; a six-hour per-frame stream
    # need not be materialized in memory again for this join.
    for source in ('direct','https'):
        with (clients/source/'frames.jsonl').open() as f:
            for line in f:
                row=json.loads(line); h=row['headers']
                grab=h.get('x-ustreamer-grab-begin-time')
                if grab not in keys:
                    unmatched_anomalies+=bool(row['anomaly'])
                    continue
                encode=h.get('x-ustreamer-encode-end-time')
                matches.setdefault(grab,[]).append(dict(source=source,index=row['index'],
                    encode_end_time=encode,sha256=row['sha256'],anomaly=row['anomaly'],
                    actual_length=row['actual_length'],trailing_hex=row['trailing_hex']))
    result=[]
    for event in events:
        b=event['boundary']
        rows=matches.get(b['grab_begin_time'],[])
        # DQBUF precedes encode: only grab time exists there. Subsequent
        # boundaries must match BOTH existing multipart timestamp headers.
        if b['stage']!='dqbuf':
            rows=[r for r in rows if r['encode_end_time']==b['encode_end_time']]
        result.append(dict(diagnostic=event, multipart_matches=[dict(r,
            payload_matches=r['sha256']==b['sha256'],
            tail_matches=r['trailing_hex']==event['jpeg']['trailing_hex']) for r in rows]))
    summary_path=diagnostics/'summary.json'
    summary=json.loads(summary_path.read_text()) if summary_path.exists() else None
    normal_evidence=[]
    for row in recent:
        b=row['boundary']
        linked=[dict(r,payload_matches=r['sha256']==b['sha256'])
                for r in matches.get(b['grab_begin_time'],[]) if r['anomaly'] and
                (b['stage']=='dqbuf' or r['encode_end_time']==b['encode_end_time'])]
        if linked:
            normal_evidence.append(dict(**row,multipart_matches=linked))
    return dict(qualification='NOT_RUN', events=result, diagnostic_summary=summary,
                recent_boundary_matches=normal_evidence,
                multipart_anomalies_without_capture_key=unmatched_anomalies,
                clean_shutdown_summary_present=summary is not None,
                interpretation='Missing records are not proof of a clean boundary. DHT insertion can change HW-JPEG hashes. Header shape alone does not identify origin.')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--diagnostics',type=Path,required=True)
    p.add_argument('--clients',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    with a.output.open('x') as f:
        json.dump(correlate(a.diagnostics,a.clients),f,indent=2); f.write('\n')
