#!/usr/bin/env python3
"""Execute on target through authenticated SSH; use only kvmd's native Unix API."""
import asyncio
import hashlib
import io
import json
import time
import aiohttp
from PIL import Image

SOCKET='/run/kvmd/api/kvmd.sock'
async def qualify():
    result={'result':'failed','socket':SOCKET,'snapshots':[],'websockets':[]}
    async with aiohttp.ClientSession(connector=aiohttp.UnixConnector(path=SOCKET),
                                     timeout=aiohttp.ClientTimeout(total=15)) as session:
        async def state(path):
            async with session.get('http://localhost'+path) as response:
                response.raise_for_status()
                data=await response.json()
                assert data['ok'], data
                return data['result']
        result['info']=await state('/info?legacy=false')
        assert result['info']['system']['platform']['type']=='blikvm'
        before=await state('/streamer'); result['state_before']=before
        assert before['streamer']['source']['online'], before
        assert before['streamer']['source']['resolution']=={'width':1920,'height':1080}, before
        assert before['params']['desired_fps']==30, before
        for i in range(3):
            async with session.ws_connect('http://localhost/ws?stream=true') as ws:
                events=[]
                while not {'loop','streamer','clients'}.issubset({e['event_type'] for e in events}):
                    msg=await asyncio.wait_for(ws.receive_json(),10)
                    events.append(msg)
                await ws.send_json({'event_type':'ping','event':{}})
                while True:
                    msg=await asyncio.wait_for(ws.receive_json(),10)
                    events.append(msg)
                    if msg['event_type']=='pong': break
                result['websockets'].append(events)
            await asyncio.sleep(.2)
        for i in range(12):
            async with session.get('http://localhost/streamer/snapshot'+('?save=true' if i==0 else '')) as response:
                response.raise_for_status(); data=await response.read()
                assert response.content_type=='image/jpeg'
                with Image.open(io.BytesIO(data)) as picture:
                    assert picture.size==(1920,1080); picture.verify()
                result['snapshots'].append({'time':time.monotonic(),'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()})
            await asyncio.sleep(.2)
        assert len({s['sha256'] for s in result['snapshots']})>=8, result['snapshots']
        saved=await state('/streamer'); assert saved['snapshot']['saved'] is not None
        result['saved_state']=saved
        async with session.delete('http://localhost/streamer/snapshot') as response:
            response.raise_for_status()
        result['state_after']=await state('/streamer')
        assert result['state_after']['snapshot']['saved'] is None
        # Excluded hardware routes must not be registered in this package.
        for path in ('/hid','/atx','/msd','/gpio','/switch','/auth/login'):
            async with session.get('http://localhost'+path) as response:
                assert response.status==404,(path,response.status)
        result['result']='passed'
    return result
if __name__=='__main__':
    try:
        print(json.dumps(asyncio.run(qualify()),sort_keys=True))
    except Exception as error:
        print(json.dumps({'result':'failed','error':repr(error)}))
        raise
