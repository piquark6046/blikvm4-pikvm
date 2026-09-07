#!/usr/bin/env python3
"""Actual HTTPS HID requests with exact grabbed host evdev verification."""
import argparse
import hashlib
import contextlib
import json
import os
from pathlib import Path
import runpy
import select
import ssl
import time
import urllib.request
import urllib.parse
import http.cookiejar

HERE=Path(__file__).resolve().parent
G4=runpy.run_path(str(HERE/'storagelab.py'))
G2=runpy.run_path(str(HERE/'absolutelab.py'))
G1=G4['G1']

class Recorder:
    def __init__(self,path): self.path=path
    def save_text(self,name,text): (self.path/name).write_text(text)

class Client:
    def __init__(self,private):
        self.private=private
        self.context=ssl.create_default_context(cafile=str(private/'ca.crt'))
        self.cookies=http.cookiejar.CookieJar()
        self.opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.cookies),urllib.request.HTTPSHandler(context=self.context))
    def request(self,path,params=None,login=False):
        data=None
        if login:data=urllib.parse.urlencode(params).encode()
        elif params is not None:path+='?'+urllib.parse.urlencode(params);data=b''
        req=urllib.request.Request('https://blikvm-v4.lab/api'+path,data=data)
        with self.opener.open(req,timeout=10) as response:return json.load(response)
    def login(self):
        creds=json.loads((self.private/'credentials.json').read_text())
        self.request('/auth/login',{'user':creds['user'],'passwd':creds['passwd']},True)
    def clear(self): self.request('/hid/reset',{});time.sleep(.3)



def usb_descriptors(device,rec,label):
    data=(device/'descriptors').read_bytes()
    digest=hashlib.sha256(data).hexdigest()
    (rec.path/(label+'-usb-descriptors.bin')).write_bytes(data)
    assert digest=='733b5003b2c57a865b6366a1e4a8aa6429e9a6d3a827a79b64ba8473b445a52e','frozen USB descriptor mismatch'
    return digest


def drain(cap):
    events=[]
    while select.select([cap.fd],[],[],0)[0]:
        events+=G1['decode_input'](os.read(cap.fd,G1['INPUT_EVENT'].size*128))
    return events


def frames(events):
    result=[];frame=[]
    for event in events:
        triple=[event['type'],event['code'],event['value']]
        if triple==[0,0,0]:result.append(frame);frame=[]
        elif triple[:2]==[4,4]:continue
        else:frame.append(triple)
    assert not frame,'missing final SYN_REPORT'
    return result


def released(caps):
    for cap in caps:
        assert not G2['bits'](G2['ioctl_read'](cap.fd,0x18,96)), 'held keys/buttons: '+str(cap.identity)


def main():
    p=argparse.ArgumentParser();p.add_argument('--private-dir',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--keep-session',action='store_true');a=p.parse_args()
    a.output.mkdir(parents=True,exist_ok=False)
    (a.output/('source-'+Path(__file__).name)).write_bytes(Path(__file__).read_bytes())
    rec=Recorder(a.output)
    result={'result':'failed','checks':[]};client=Client(a.private_dir)
    monitor=G1['HostMonitor'](rec)
    try:
        device=G4['wait_device'](True,20)
        result['descriptors']=G4['exact_descriptors'](device,rec,'api')
        result['usb']=G4['details'](device)
        result['usb_descriptor_sha256']=usb_descriptors(device,rec,'api')
        monitor.start()
        with contextlib.ExitStack() as stack:
            caps=[stack.enter_context(G4['Capture'](device,rec,i)) for i in range(3)]
            result['evdev']=[c.identity for c in caps]
            G4['mouse_caps'](caps[1].fd);G4['relative_caps'](caps[2].fd)
            def cleanup_grabbed():
                client.login();client.clear();released(caps)
                rec.save_text('cleanup-events.json',json.dumps([drain(c) for c in caps]))
            stack.callback(cleanup_grabbed)
            client.login();client.clear();released(caps)
            for c in caps:drain(c)
            result['authorization']=[]
            def denied(who,label,path,params,login=False):
                try:who.request(path,params,login)
                except urllib.error.HTTPError as e:
                    assert e.code in (401,403),(label,e.code)
                    result['authorization'].append({'case':label,'status':e.code})
                else:raise AssertionError(label+' accepted')
                time.sleep(.1)
                assert [frames(drain(c)) for c in caps]==[[],[],[]],label+' emitted input'
            unauthorized=Client(a.private_dir)
            denied(unauthorized,'unauth-keyboard','/hid/events/send_key',{'key':'KeyA','state':1})
            denied(unauthorized,'unauth-absolute','/hid/events/send_mouse_move',{'to_x':1000,'to_y':2000})
            denied(unauthorized,'unauth-relative','/hid/events/send_mouse_relative',{'delta_x':9,'delta_y':0})
            denied(unauthorized,'invalid-credentials','/auth/login',{'user':'invalid-m8d','passwd':'invalid-m8d'},True)
            def run(label,requests,expected):
                for path,params in requests:
                    client.request(path,params);time.sleep(.12)
                time.sleep(.2)
                raw=[drain(c) for c in caps];actual=[frames(e) for e in raw]
                rec.save_text(label+'.json',json.dumps({'events':raw,'actual':actual,'expected':expected},indent=2))
                assert actual==expected,label+': '+str(actual)
                released(caps)
                result['checks'].append(label)
            result['excluded_routes']=[]
            for route in ('/hid/print','/hid/events/send_shortcut','/msd/reset','/atx/power','/gpio/switch'):
                try:client.request(route,{})
                except urllib.error.HTTPError as e:
                    assert e.code==404,(route,e.code)
                    result['excluded_routes'].append({'route':route,'status':e.code})
                else:raise AssertionError(route+' exposed')
            key='/hid/events/send_key'
            seq=[('ShiftLeft',1),('ShiftLeft',0),('KeyA',1),('KeyA',0),
                 ('ShiftLeft',1),('KeyA',1),('KeyA',0),('ShiftLeft',0),
                 ('KeyA',1),('KeyA',1),('KeyA',0)]
            key_events=[(42,1),(42,0),(30,1),(30,0),(42,1),(30,1),(30,0),(42,0),
                        (30,1),(30,0),(30,1),(30,0)]
            run('keyboard',[(key,{'key':k,'state':v}) for k,v in seq],
                [[[[1,k,v]] for k,v in key_events],[],[]])
            move='/hid/events/send_mouse_move';button='/hid/events/send_mouse_button'
            client.request('/hid/set_params',{'mouse_output':'usb'});time.sleep(.2)
            for c in caps:drain(c)
            points=[(-32256,-31744),(0,-16384),(32256,31744)]
            req=[(move,{'to_x':x,'to_y':y}) for x,y in points]
            req += [(button,{'button':'left','state':1}),(button,{'button':'left','state':0})]
            # Upstream linear remap truncates toward zero.
            coords=[(int((x+32768)*32767/65535),int((y+32768)*32767/65535)) for x,y in points]
            expected=[[[3,0,x],[3,1,y]] for x,y in coords]+[[[1,272,1]],[[1,272,0]]]
            run('absolute',req,[[],expected,[]])
            for index,mode in enumerate(['usb_rel','usb','usb_rel','usb']):
                client.request('/hid/set_params',{'mouse_output':mode});time.sleep(.25)
                released(caps)
                for c in caps:drain(c)
                state=client.request('/hid')['result']
                assert state['mouse']['outputs']['active']==mode
                if mode=='usb_rel':
                    deltas=[(9,0),(-9,0),(0,7),(0,-7),(5,-4)]
                    req=[('/hid/events/send_mouse_relative',{'delta_x':x,'delta_y':y}) for x,y in deltas]
                    expected=[[[2,axis,v] for axis,v in enumerate(pair) if v] for pair in deltas]
                    req += [(button,{'button':'left','state':1}),(button,{'button':'left','state':0})]
                    expected += [[[1,272,1]],[[1,272,0]]]
                    run('relative-switch-'+str(index),req,[[],[],expected])
                else:
                    x=1000+index;y=2000+index
                    px=int((x+32768)*32767/65535);py=int((y+32768)*32767/65535)
                    run('absolute-switch-'+str(index),[(move,{'to_x':x,'to_y':y})],[[],[[[3,0,px],[3,1,py]]],[]])
            client.clear();released(caps)
            if not a.keep_session:
                client.request('/auth/logout',{})
                for c in caps:drain(c)
                denied(client,'logged-out-keyboard','/hid/events/send_key',{'key':'KeyA','state':1})
                denied(client,'logged-out-mouse','/hid/events/send_mouse_button',{'button':'left','state':1})
            result['result']='passed'
    except Exception as e:result['error']=str(e)
    finally:
        monitor.stop()
        rec.save_text('result.json',json.dumps(result,indent=2)+'\n')
    print(json.dumps(result));return result['result']=='passed'

if __name__=='__main__':raise SystemExit(not main())
