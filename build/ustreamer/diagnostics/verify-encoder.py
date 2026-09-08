#!/usr/bin/env python3
"""Compare original HW-JPEG output to patched output, with diagnostics on/off."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]


def without_dht(data):
    result=data[:2];i=2
    while data[i:i+2] != b'\xff\xda':
        assert data[i]==255
        length=int.from_bytes(data[i+2:i+4],'big')+2
        if data[i+1]!=196: result+=data[i:i+length]
        i+=length
    return result+data[i:]


def verify(base,patched,out):
    out.mkdir(parents=True,exist_ok=False)
    for name,source in (('base',base),('patched',patched)):
        command=['cc','-D_GNU_SOURCE','-std=c17','-O2','-Wall','-Wextra','-Werror',
                 '-I'+str(source/'src'),str(HERE/'encoder-driver.c'),
                 str(source/'src/libs/frame.c'),str(source/'src/ustreamer/encoders/hw/encoder.c')]
        if name=='patched':command+=[str(source/'src/libs/taildiag.c'),'-lcrypto','-pthread']
        subprocess.run(command+['-lm','-o',str(out/name)],check=True)
    original=(ROOT/'tests/fixtures/m8f0/observed-trailing-data.jpg').read_bytes()
    results=[]
    for name,data in (('exact',original[:-12]),('preserved',original),
                      ('zero',original[:-12]+bytes(12)),('garbage',original[:-12]+b'garbage')):
        for dht,payload in (('with-dht',data),('without-dht',without_dht(data))):
            key=name+'-'+dht;source=out/(key+'.input');source.write_bytes(payload)
            assert (b'\xff\xc4' in payload[:2048]) == (dht=='with-dht')
            hashes={};lengths={}
            for mode in ('base','off','on'):
                env=os.environ.copy();env.pop('USTREAMER_TAILDIAG_DIR',None)
                if mode=='on':
                    logs=out/(key+'-logs');logs.mkdir(mode=0o700)
                    env['USTREAMER_TAILDIAG_DIR']=str(logs)
                dest=out/(key+'.'+mode)
                subprocess.run([str(out/('base' if mode=='base' else 'patched')),str(source),str(dest)],env=env,check=True)
                output=dest.read_bytes();hashes[mode]=hashlib.sha256(output).hexdigest();lengths[mode]=len(output)
                assert output.endswith(data[-12:])
            assert len(set(hashes.values()))==1,(key,hashes)
            assert source.read_bytes()==payload
            if dht=='without-dht': assert lengths['base']>len(payload)
            results.append(dict(fixture=key,input_sha256=hashlib.sha256(payload).hexdigest(),
                                input_bytes=len(payload),output_sha256=hashes,output_bytes=lengths))
    report=dict(result='passed',qualification='NOT_RUN',comparisons=results)
    (out/'result.json').write_text(json.dumps(report,indent=2)+'\n')
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--baseline',type=Path,required=True);p.add_argument('--patched',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    print(json.dumps(verify(a.baseline.resolve(),a.patched.resolve(),a.output.resolve()),indent=2))
