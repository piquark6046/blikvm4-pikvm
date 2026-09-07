#!/usr/bin/env node
// Direct isolated LAN qualification with normal browser certificate verification.
// Credentials and cookies are never included in public results or traces.
import fs from 'node:fs';
import path from 'node:path';
import tls from 'node:tls';
import crypto from 'node:crypto';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {spawn} from 'node:child_process';
const require = createRequire(import.meta.url);
const {chromium} = require(path.resolve('out/kvmd-web/browser/node_modules/playwright'));
const [privateDir, output, secondsText='120'] = process.argv.slice(2);
assert(privateDir && output);
const seconds = Number(secondsText);
assert(seconds >= 5);
fs.mkdirSync(output, {recursive:false});
const credentials = JSON.parse(fs.readFileSync(path.join(privateDir, 'credentials.json')));
const ca = fs.readFileSync(path.join(privateDir, 'ca.crt'));
const base = 'https://blikvm-v4.lab';
const result = {result:'failed', http:[], websockets:[], browser:{assets:[], errors:[]}};
const runner=fs.readFileSync(new URL(import.meta.url));
fs.writeFileSync(path.join(output,'runner.mjs'),runner);
result.automation_sha256=crypto.createHash('sha256').update(runner).digest('hex');
let browser;
const cookieFile = path.join(privateDir, 'stream-curl.conf');
try {
    result.tls = await new Promise((resolve,reject) => {
        const socket = tls.connect({host:'192.168.88.2', port:443, servername:'blikvm-v4.lab', ca}, () => {
            const cert=socket.getPeerCertificate();
            const expected=new crypto.X509Certificate(fs.readFileSync(path.join(privateDir,'server.crt'))).fingerprint256;
            try { assert.equal(cert.fingerprint256,expected); assert(socket.authorized); }
            catch(e) { socket.destroy(); reject(e); return; }
            resolve({protocol:socket.getProtocol(), fingerprint256:cert.fingerprint256,
                     subject:cert.subject, subjectaltname:cert.subjectaltname, verified:true});
            socket.end();
        });
        socket.setTimeout(10000,()=>socket.destroy(new Error('TLS timeout')));
        socket.on('error',reject);
    });
    browser = await chromium.launch({headless:true,args:['--host-resolver-rules=MAP wrong.blikvm-v4.lab 192.168.88.2']});
    result.browser.version=browser.version();
    const negativeContext=await browser.newContext({ignoreHTTPSErrors:false});
    const negativePage=await negativeContext.newPage();
    let rejected=false;
    try { await negativePage.goto('https://wrong.blikvm-v4.lab/login/',{timeout:10000}); }
    catch(e) { assert(e.message.includes('ERR_CERT_COMMON_NAME_INVALID'),e.message); rejected=true; }
    assert(rejected,'browser accepted wrong-name certificate');
    result.browser.wrong_name_rejected=true;
    await negativeContext.close();
    // Dedicated CA is installed in the bridge user NSS trust database; no bypass.
    const ctx=await browser.newContext({ignoreHTTPSErrors:false});
    async function status(label,method,url,expected,form) {
        const r=await ctx.request.fetch(base+url,{method,form,maxRedirects:0});
        result.http.push({label,method,path:url,status:r.status()});
        assert(expected.includes(r.status()),label+': '+r.status());
        return r;
    }
    async function ws(label, expected) {
        const page=await ctx.newPage();
        await page.goto(base+'/login/');
        const r=await page.evaluate(() => new Promise(resolve => {
            const socket=new WebSocket('wss://blikvm-v4.lab/api/ws');
            const events=[]; let done=false;
            const finish=(ok)=>{if(done)return;done=true;socket.close();resolve({ok,events});};
            const timer=setTimeout(()=>finish(false),12000);
            socket.onmessage=e=>{if(typeof e.data==='string'){
                const value=JSON.parse(e.data);events.push(value.event_type);
                if(value.event_type==='streamer') socket.send(JSON.stringify({event_type:'ping',event:{}}));
                if(value.event_type==='pong'){clearTimeout(timer);finish(true);}
            }};
            socket.onerror=()=>{clearTimeout(timer);finish(false);};
        }));
        result.websockets.push({label,...r});
        assert.equal(r.ok,expected,label);
        await page.close();
    }
    await status('unauthenticated API','GET','/api/streamer',[401]);
    await status('unauthenticated web redirected to login','GET','/kvm/',[302]);
    await status('unauthenticated video','GET','/streamer/state',[401]);
    await ws('unauthenticated',false);
    await status('invalid credentials','POST','/api/auth/login',[403],{user:credentials.user,passwd:'invalid-qualification-password'});
    await status('valid credentials','POST','/api/auth/login',[200],credentials);
    await status('authenticated API','GET','/api/streamer',[200]);
    await status('authenticated video','GET','/streamer/state',[200]);
    await ws('authenticated',true);
    for(const name of ['hid','msd','atx','gpio','switch'])
        await status('excluded '+name,'GET','/api/'+name,[404]);
    for(const name of ['vnc','ipmi'])
        await status('excluded page '+name,'GET','/'+name+'/',[404]);
    await status('logout','POST','/api/auth/logout',[200]);
    await status('logged-out API','GET','/api/streamer',[401,403]);
    await status('logged-out video','GET','/streamer/state',[401,403]);
    await ws('logged-out',false);
    await ctx.close();

    const ui=await browser.newContext({ignoreHTTPSErrors:false,viewport:{width:1440,height:1000}});
    const page=await ui.newPage();
    const webSockets=[];
    page.on('pageerror',e=>result.browser.errors.push(e.message));
    page.on('response',r=>{
        const u=new URL(r.url());
        if(u.pathname.startsWith('/share/')||['document','stylesheet','script','font'].includes(r.request().resourceType()))
            result.browser.assets.push({path:u.pathname,status:r.status()});
    });
    page.on('websocket',socket=>{
        const record={path:new URL(socket.url()).pathname,events:[]};webSockets.push(record);
        socket.on('framereceived',({payload})=>{if(typeof payload==='string') {
            try{record.events.push(JSON.parse(payload).event_type);}catch{}
        }});
    });
    page.on('dialog',d=>d.accept());
    await page.goto(base+'/kvm/');
    await page.waitForURL('**/login/');
    await page.locator('#user-input').fill(credentials.user);
    await page.locator('#passwd-input').fill(credentials.passwd);
    await page.locator('#login-button').click();
    await page.waitForURL(base+'/');
    await page.locator('a[href$="kvm/"]').click();
    async function moving(label) {
        await page.waitForFunction(()=>document.querySelector('#link-led')?.title==='Connected');
        await page.waitForFunction(()=>document.querySelector('#stream-image')?.naturalWidth===1920);
        const samples=[];
        for(let i=0;i<6;i++){
            const png=await page.evaluate(()=>{
                const img=document.querySelector('#stream-image');
                const c=document.createElement('canvas');c.width=img.naturalWidth;c.height=img.naturalHeight;
                if(c.width!==1920||c.height!==1080)throw Error('unexpected video dimensions');
                c.getContext('2d').drawImage(img,0,0);return c.toDataURL();
            });
            samples.push(crypto.createHash('sha256').update(png).digest('hex'));
            await new Promise(r=>setTimeout(r,500));
        }
        assert(new Set(samples).size>=4,label+' moving browser frames');
        result.browser[label]={width:1920,height:1080,hashes:samples};
    }
    await moving('initial');
    await page.screenshot({path:path.join(output,'browser.png')});
    await page.reload({waitUntil:'domcontentloaded'});
    await moving('reload');
    const cookie=(await ui.cookies()).find(x=>x.name==='auth_token');
    assert(cookie?.secure && cookie.httpOnly && cookie.sameSite==='Strict');
    result.browser.cookie={secure:cookie.secure,httpOnly:cookie.httpOnly,sameSite:cookie.sameSite};
    // Match M8-A's one-video-client rate load. The authenticated real browser
    // remains on the index while this bounded client measures the same nginx
    // MJPEG route. Motion/reload are exercised in Chromium on both sides.
    await page.goto(base+'/');
    await page.locator('#logout-button').waitFor();
    result.rate_load={video_clients:1,browser_page:'authenticated index',path:'bridge enp1s0 192.168.88.1 -> target eth0 192.168.88.2:443',tunnel:false};
    fs.writeFileSync(cookieFile,`cookie = "auth_token=${cookie.value}"\n`,{mode:0o600});
    const args=['lab/stream-client.py','--seconds',String(seconds),'--out',path.join(output,'stream'),
                '--','curl','--config',cookieFile,'--cacert',path.join(privateDir,'ca.crt'),
                '--silent','--show-error','--no-buffer','--include','--max-time',String(seconds+10),
                base+'/streamer/stream'];
    await new Promise((resolve,reject)=>{
        const proc=spawn('python3',args,{stdio:['ignore','ignore','inherit']});
        proc.on('error',reject);proc.on('close',code=>code===0?resolve():reject(Error('web stream gate failed')));
    });
    const stream=JSON.parse(fs.readFileSync(path.join(output,'stream/result.json')));
    assert(stream.frames/stream.elapsed>=27,'delivered video must be >=27 fps');
    result.stream={seconds,frames:stream.frames,fps:stream.frames/stream.elapsed,unique_hashes:stream.unique_hashes};
    await page.locator('a[href$="kvm/"]').click();
    await moving('after_rate_gate');
    result.browser.websockets=webSockets;
    assert(webSockets.some(x=>x.events.includes('streamer')));
    assert.equal(result.browser.errors.length,0);
    assert(result.browser.assets.length>10);
    assert(result.browser.assets.every(x=>x.status<400));
    if(process.env.WEB_LIFECYCLE_DIR) {
        const control=process.env.WEB_LIFECYCLE_DIR;
        fs.mkdirSync(control,{recursive:false});
        async function phase(name) {
            fs.writeFileSync(path.join(control,name+'-ready'),'ready\n');
            const start=Date.now();
            while(!fs.existsSync(path.join(control,name+'-done'))) {
                if(Date.now()-start>180000)throw Error('lifecycle coordinator timeout: '+name);
                await new Promise(r=>setTimeout(r,250));
            }
        }
        await phase('nginx-restart');
        await moving('nginx_restart');
        assert.equal((await ui.request.get(base+'/api/auth/check')).status(),200);
        await phase('kvmd-restart');
        result.browser.kvmd_restart_statuses=[];
        for(let i=0;i<100;i++) {
            const code=(await ui.request.get(base+'/api/auth/check')).status();
            result.browser.kvmd_restart_statuses.push(code);
            if([401,403].includes(code))break;
            assert([502,503].includes(code),'unexpected authentication state after kvmd restart: '+code);
            await new Promise(r=>setTimeout(r,200));
        }
        assert([401,403].includes(result.browser.kvmd_restart_statuses.at(-1)));
        await page.locator('[data-x-wm-modal-ok]').click({timeout:30000});
        await page.waitForURL('**/login/');
        await page.locator('#user-input').fill(credentials.user);
        await page.locator('#passwd-input').fill(credentials.passwd);
        await page.locator('#login-button').click();
        await page.waitForURL(base+'/');
        await page.locator('a[href$="kvm/"]').click();
        await moving('kvmd_restart_reauthenticated');
        await phase('hdmi-off');
        const loss=[];
        for(let i=0;i<4;i++) {
            const response=await ui.request.get(base+'/api/streamer/snapshot');
            assert.equal(response.status(),200);
            loss.push(crypto.createHash('sha256').update(await response.body()).digest('hex'));
            await new Promise(r=>setTimeout(r,500));
        }
        assert.equal(new Set(loss).size,1,'expected static MS2131 no-signal video');
        result.browser.hdmi_loss={hashes:loss,api_healthy:true};
        await phase('hdmi-on');
        await moving('hdmi_recovered');
        result.browser.lifecycle=true;
    }
    // Exercise the actual upstream index-page logout action.
    await page.goto(base+'/');
    await page.locator('#logout-button').click();
    await page.waitForURL('**/login/');
    assert([401,403].includes((await ui.request.get(base+'/api/auth/check')).status()));
    result.browser.logout=true;
    assert.equal(result.browser.errors.length,0);
    assert(result.browser.assets.every(x=>x.status<400));
    result.result='passed';
} catch(e) {
    result.error=e.stack;
} finally {
    fs.rmSync(cookieFile,{force:true});
    if(browser)await browser.close();
    fs.writeFileSync(path.join(output,'result.json'),JSON.stringify(result,null,2)+'\n');
}
console.log(JSON.stringify({result:result.result,output,error:result.error}));
process.exitCode=result.result==='passed'?0:1;
