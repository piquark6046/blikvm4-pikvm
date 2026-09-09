#!/usr/bin/env python3
"""M8-F0 diagnostic snapshot parser and bounded target collector. No video changes."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import struct
import time


def layout(schema):
    sizes={}
    for kind in ('packet','copy'):
        sizes[kind]=8*len(schema[kind+'_fields'])+64*len(schema[kind+'_arrays'])
    sizes['header']=8*len(schema['event_fields'])
    sizes['frame']=sizes['header']+schema['ring']*(sizes['packet']+sizes['copy'])
    return sizes


def decode(data,schema):
    sizes=layout(schema)
    if len(data)<sizes['frame']:raise ValueError('partial event')
    h=dict(zip(schema['event_fields'],struct.unpack_from('<'+'q'*len(schema['event_fields']),data)))
    if h['version']!=schema['version']:raise ValueError('ABI version mismatch')
    if not 0<=h['bytesused']<=schema['frame_max'] or len(data)!=sizes['frame']+h['bytesused']:
        raise ValueError('partial or oversized completed payload')
    payload=data[sizes['frame']:]
    if not 0<=h['final_eoi']<=len(payload)-2 or payload[h['final_eoi']:h['final_eoi']+2]!=b'\xff\xd9':
        raise ValueError('EOI mismatch')
    if h['tail_length']!=len(payload)-h['final_eoi']-2 or h['tail_length']<=0:raise ValueError('tail mismatch')
    rows={};offset=sizes['header']
    for kind,countkey in (('packet','packet_count'),('copy','copy_count')):
        count=h[countkey]
        if not 0<=count<=schema['ring']:raise ValueError('ring count out of bounds')
        records=[]
        for i in range(count):
            start=offset+i*sizes[kind]
            names=schema[kind+'_fields'];r=dict(zip(names,struct.unpack_from('<'+'q'*len(names),data,start)))
            start+=len(names)*8
            for name in schema[kind+'_arrays']:
                r[name]=data[start:start+64].hex();start+=64
            records.append(r)
        rows['copies' if kind=='copy' else 'packets']=records;offset+=schema['ring']*sizes[kind]
    tail=payload[h['final_eoi']+2:]
    packets={r['id']:r for r in rows['packets']}
    copies=[r for r in rows['copies'] if r['sequence']==h['sequence'] and r['buffer_index']==h['buffer_index']]
    copies.sort(key=lambda r:r['destination_offset'])
    errors=[];cursor=0;segments=[]
    if h['required_lost']:errors.append('kernel reports required ring evidence lost')
    for c in copies:
        if c['destination_offset']!=cursor:errors.append('copy destination gap or overlap')
        cursor=c['destination_offset']+c['length']
        p=packets.get(c['packet_id'])
        if p is None:
            errors.append('source packet ring entry missing');continue
        if (p['source_offset'],p['copy_length'],p['before'])!=(c['source_offset'],c['length'],c['destination_offset']):
            errors.append('scheduled copy identity mismatch')
        lo=max(c['destination_offset'],h['final_eoi']+2);hi=min(cursor,len(payload))
        if lo>=hi:continue
        rel=lo-c['destination_offset'];n=hi-lo
        def edge(row,first,last,length,position,count):
            k=min(64,length)
            if position>=0 and position+count<=k:return bytes.fromhex(row[first])[position:position+count]
            if position>=length-k and position+count<=length:
                start=position-(length-k);return bytes.fromhex(row[last])[start:start+count]
            return None
        source=c['source_offset']+rel
        raw=edge(p,'raw_first','raw_last',p['actual_length'],source-p['transfer_offset'],n)
        selected=edge(p,'selected_first','selected_last',c['length'],rel,n)
        before=edge(c,'source_first','source_last',c['length'],rel,n)
        after=edge(c,'destination_first','destination_last',c['length'],rel,n)
        expected=payload[lo:hi]
        if any(x is None for x in (raw,selected,before,after)):errors.append('tail bytes outside retained boundary windows')
        segments.append({'packet_id':p['id'],'destination_offset':lo,'length':n,'expected_hex':expected.hex(),
            'raw_hex':None if raw is None else raw.hex(),'selected_hex':None if selected is None else selected.hex(),
            'pre_memcpy_source_hex':None if before is None else before.hex(),
            'post_memcpy_destination_hex':None if after is None else after.hex(),
            'all_equal':all(x==expected for x in (raw,selected,before,after)),
            'source_offset_in_packet':source-p['transfer_offset'],'decoded_header_length':p['decoded_header'],
            'header_present':bool(p['header_present'])})
    if cursor!=len(payload):errors.append('completed bytes not fully covered by copy ring')
    if sum(s['length'] for s in segments)!=len(tail):errors.append('tail copy coverage incomplete')
    return {'header':h,**rows,'complete_sha256':hashlib.sha256(payload).hexdigest(),
        'through_eoi_sha256':hashlib.sha256(payload[:h['final_eoi']+2]).hexdigest(),
        'tail_hex':tail.hex(),'correlation_segments':segments,'evidence_gaps':errors,
        'classification':'D' if errors else 'REQUIRES_CROSS_LAYER_REVIEW'},payload


def collect(args):
    os.umask(0o077);args.output.mkdir(exist_ok=False)
    schema=json.loads(args.schema.read_text());sizes=layout(schema)
    roots=list(Path('/sys/kernel/debug/usb/uvcvideo').glob('*/taildiag-state'))
    assert len(roots)==1,roots
    root=roots[0].parent;deadline=time.monotonic()+args.seconds
    seen=set();total=0
    result={'result':'failed','qualification':'NOT_RUN'}
    def state():
        text=roots[0].read_text();d={k:int(v) for k,v in (x.split('=') for x in text.split())}
        assert d['packet_size']==sizes['packet'] and d['copy_size']==sizes['copy'] and d['event_header_size']==sizes['header']
        return d
    try:
        (args.output/'initial-state.json').write_text(json.dumps(state(),indent=2)+'\n')
        while time.monotonic()<deadline:
            for p in sorted(root.glob('taildiag-event*')):
                data=p.read_bytes()
                if not data:continue
                total+=len(data)
                assert total<=64*1024*1024,'bounded collector storage exhausted'
                report,payload=decode(data,schema);event=report['header']['id']
                assert event not in seen,'duplicate snapshot';seen.add(event)
                folder=args.output/f'event-{event:06d}';folder.mkdir()
                for name,body in [('kernel.bin',data),('completed.bin',payload),('decoded.json',(json.dumps(report,indent=2)+'\n').encode())]:
                    partial=folder/(name+'.partial');partial.write_bytes(body);partial.rename(folder/name)
                # The immutable files exist before the ID-specific kernel acknowledgement.
                with p.open('w') as f:f.write(str(event))
                assert not report['evidence_gaps'],report['evidence_gaps']
            current=state()
            (args.output/'state.json').write_text(json.dumps(current,indent=2)+'\n')
            assert current['suppressed']==current['required_lost']==current['oversized']==0,'kernel evidence gap'
            if args.stop_after_event and seen:break
            if args.stop_file and args.stop_file.exists():break
            time.sleep(.1)
        result.update(result='collected',events=len(seen),bytes=total,state=state())
    except Exception as ex:result['error']=str(ex)
    finally:
        (args.output/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--schema',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--seconds',type=int,default=360)
    p.add_argument('--stop-after-event',action='store_true');p.add_argument('--stop-file',type=Path);a=p.parse_args()
    assert 1<=a.seconds<=86400
    print(json.dumps(collect(a)))
