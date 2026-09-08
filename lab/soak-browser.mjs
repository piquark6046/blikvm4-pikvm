#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url);
const {chromium}=require(path.resolve('out/kvmd-web/browser/node_modules/playwright'));
const [privateDir,out]=process.argv.slice(2);
const credentials=JSON.parse(fs.readFileSync(path.join(privateDir,'credentials.json')));
const base='https://blikvm-v4.lab';
const pause=ms=>new Promise(r=>setTimeout(r,ms));
const mono=()=>Number(process.hrtime.bigint())/1e9;
// Playwright request errors include a call log containing request cookies.
// Redact strings before serialization, including both evidence and final errors.
const scrub=v=>typeof v==='string'?v.split(credentials.passwd).join('<redacted-password>').replace(/(?:cookie:|set-cookie:)\s*auth_token=[^\s;"']+/gi,'[session header redacted]').replace(/auth_token=[^\s;"']+/gi,'auth_token=<redacted>'):v;
const encode=v=>JSON.stringify(v,(_key,value)=>scrub(value));
const write=(name,v)=>{const p=path.join(out,name);fs.writeFileSync(p+'.tmp',encode(v));fs.renameSync(p+'.tmp',p);};
const log=v=>fs.appendFileSync(path.join(out,'browser-samples.jsonl'),encode(v)+'\n');
const control=()=>JSON.parse(fs.readFileSync(path.join(out,'control.json')));
let browser;
const result={result:'failed'};
try {
 browser=await chromium.launch({headless:false});result.version=browser.version();
 const ctx=await browser.newContext({ignoreHTTPSErrors:false,viewport:{width:1440,height:1000}});
 const page=await ctx.newPage();page.setDefaultTimeout(15000);page.setDefaultNavigationTimeout(15000);
 page.on('pageerror',e=>log({t:mono(),pageerror:e.message,planned:control().until>mono()}));
 page.on('dialog',d=>d.accept());
 async function login(){
  await page.goto(base+'/login/');
  await page.waitForFunction(()=>typeof document.querySelector('#login-button')?.onclick==='function');
  await page.locator('#user-input').fill(credentials.user);await page.locator('#passwd-input').fill(credentials.passwd);
  await page.locator('#login-button').click();await page.waitForURL(base+'/');
  await page.goto(base+'/kvm/');
  await page.waitForFunction(()=>document.querySelector('#link-led')?.title==='Connected');
  await page.waitForFunction(()=>document.querySelector('#stream-image')?.naturalWidth===1920);
 }
 await login();await page.screenshot({path:path.join(out,'browser-initial.png')});
 let lastHash='',changed=mono(),lastEvent='';
 while(!fs.existsSync(path.join(out,'stop'))){
  const c=control(),planned=c.until>mono();
  try {
   if(c.event==='logout'&&c.id!==lastEvent){
    lastEvent=c.id;
    await page.goto(base+'/');await page.locator('#logout-button').click();
    const denied=await ctx.request.get(base+'/api/msd');assert([401,403].includes(denied.status()));
    log({t:mono(),event:'logout-denied',status:denied.status(),id:c.id});
    await login();write('browser-event.json',{id:c.id,result:'passed',t:mono()});
   }
   const value=await page.evaluate(()=>{
    const im=document.querySelector('#stream-image');
    if(document.querySelector('#link-led')?.title!=='Connected'||im?.naturalWidth!==1920||im?.naturalHeight!==1080)throw Error('UI stream/session not ready');
    const canvas=document.createElement('canvas');canvas.width=192;canvas.height=108;
    canvas.getContext('2d').drawImage(im,0,0,192,108);
    return {width:im.naturalWidth,height:im.naturalHeight,pixels:canvas.toDataURL(),connected:true};
   });
   const hash=crypto.createHash('sha256').update(value.pixels).digest('hex');delete value.pixels;
   if(hash!==lastHash){changed=mono();lastHash=hash;}
   assert(planned||mono()-changed<5,'Web UI motion frozen for 5 seconds');
   const api=await ctx.request.get(base+'/api/msd');assert.equal(api.status(),200);
   log({t:mono(),...value,sha256:hash,planned,api_status:api.status()});
   write('browser-heartbeat.json',{t:mono(),planned,sha256:hash});
  } catch(e){
   log({t:mono(),error:String(e),planned:control().until>mono()});
   if(control().until<=mono())throw e;
   // Planned daemon restart/logout can revoke sessions. Normal trust/login remains required.
   try {await login();changed=mono();}catch(re){log({t:mono(),readiness:String(re),planned:true});}
  }
  await pause(1000);
 }
 await page.screenshot({path:path.join(out,'browser-final.png')});
 result.result='completed_pending_replay';
}catch(e){result.error=String(e);}
finally{if(browser)await browser.close();write('browser-result.json',result);}
process.exit(result.result==='failed'?1:0);
