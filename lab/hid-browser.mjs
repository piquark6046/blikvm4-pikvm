#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import assert from 'node:assert/strict';
import crypto from 'node:crypto';
import {execFileSync} from 'node:child_process';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url);
const {chromium}=require(path.resolve('out/kvmd-web/browser/node_modules/playwright'));
const [privateDir,out,workload]=process.argv.slice(2);
const credentials=JSON.parse(fs.readFileSync(path.join(privateDir,'credentials.json')));
const base='https://blikvm-v4.lab';let browser;let index=0;
const result={result:'failed',steps:[],errors:[]};let sent=[];
const pause=ms=>new Promise(r=>setTimeout(r,ms));
function publish(file,data){fs.writeFileSync(file+'.tmp',data);fs.renameSync(file+'.tmp',file);}
async function wait(file){let end=Date.now()+60000;while(!fs.existsSync(file)){assert(Date.now()<end,'host verifier timeout: '+file);await pause(40);} }
async function step(name,kind,action,options={}){
 const stem=path.join(out,String(++index).padStart(3,'0'));
 publish(stem+'.ready',JSON.stringify({name,kind,...options}));await wait(stem+'.go');
 sent=[];const details=await action()||{};await pause(250);details.sent=sent;
 publish(stem+'.done',JSON.stringify(details));await wait(stem+'.ok');
 const checked=JSON.parse(fs.readFileSync(stem+'.ok'));assert.equal(checked.result,'passed',JSON.stringify(checked));
 result.steps.push({name,kind,...details});
}
try {
 browser=await chromium.launch({headless:false});result.version=browser.version();
 const ctx=await browser.newContext({ignoreHTTPSErrors:false,viewport:{width:1440,height:1000}});
 ctx.on('page',p=>{p.on('pageerror',e=>result.errors.push(e.message));p.on('response',r=>{if(r.status()>=400)result.errors.push({status:r.status(),path:new URL(r.url()).pathname});});});
 let page=await ctx.newPage();page.on('websocket',ws=>ws.on('framesent',({payload})=>{if(Buffer.isBuffer(payload))sent.push(Array.from(payload));}));page.on('pageerror',e=>result.errors.push(e.message));page.on('dialog',d=>d.accept());
 async function login(){await page.goto(base+'/login/');await page.waitForFunction(()=>typeof document.querySelector('#login-button')?.onclick==='function');await page.locator('#user-input').fill(credentials.user);await page.locator('#passwd-input').fill(credentials.passwd);await page.locator('#login-button').click();await page.waitForURL(base+'/');}
 async function kvm(){await page.goto(base+'/kvm/');await page.waitForFunction(()=>document.querySelector('#link-led')?.title==='Connected');await page.waitForFunction(()=>document.querySelector('#stream-image')?.naturalWidth===1920);}
 async function state(){const r=await ctx.request.get(base+'/api/hid');assert.equal(r.status(),200);return (await r.json()).result;}
 async function post(url){const r=await ctx.request.post(base+'/api'+url);assert.equal(r.status(),200);}
 await step('login-and-open','setup',async()=>{await login();await kvm();await page.locator('#stream-window').focus();for(const id of ['hid-pak-button','hid-recorder-record','hid-recorder-play'])assert(await page.locator('#'+id).isDisabled(),id+' must stay disabled');});
 await step('keyboard','exact',async()=>{
  for(const [key,down] of [['ShiftLeft',1],['ShiftLeft',0],['KeyA',1],['KeyA',0],['ShiftLeft',1],['KeyA',1],['KeyA',0],['ShiftLeft',0]]){await page.keyboard[down?'down':'up'](key);await pause(100);}
  return {expected:[[[[1,42,1]],[[1,42,0]],[[1,30,1]],[[1,30,0]],[[1,42,1]],[[1,30,1]],[[1,30,0]],[[1,42,0]]],[],[]]};
 });
 async function absoluteAt(fx,fy){
  const b=await page.locator('#stream-image').boundingBox();
  const view=await page.evaluate(()=>{let e=document.querySelector('#stream-image');return {w:e.offsetWidth,h:e.offsetHeight,rw:e.naturalWidth,rh:e.naturalHeight};});
  const ratio=Math.min(view.w/view.rw,view.h/view.rh);
  const geo={x:Math.round((view.w-ratio*view.rw)/2),y:Math.round((view.h-ratio*view.rh)/2),w:Math.round(ratio*view.rw),h:Math.round(ratio*view.rh)};
  const px=Math.round(b.x+geo.x+fx*(geo.w-1)),py=Math.round(b.y+geo.y+fy*(geo.h-1));
  const remap=(pos,size)=>Math.floor((Math.round(pos*65535/(size-1)-32768)+32768)*32767/65535);
  await page.mouse.move(px,py);
  return {x:remap(Math.round(px-b.x)-geo.x,geo.w),y:remap(Math.round(py-b.y)-geo.y,geo.h),tolerance:1,view,geo,box:b,pointer:[px,py]};
 }
 for(const [n,fx,fy] of [['near-min',.02,.02],['center',.5,.5],['near-max',.98,.98]]){
  await step('absolute-'+n,'absolute',()=>absoluteAt(fx,fy));
 }
 await step('absolute-button','exact',async()=>{await page.mouse.down();await pause(100);await page.mouse.up();return {expected:[[],[[[1,272,1]],[[1,272,0]]],[]]};});
 async function switchMode(mode,n){
  await step('prepare-mode-'+n,'setup',async()=>{if(await page.evaluate(()=>!!document.pointerLockElement)){execFileSync('xdotool',['key','Escape']);await page.waitForFunction(()=>!document.pointerLockElement);}await page.locator('#system-dropdown > .menu-button').click();});
  await step('mode-'+mode+'-'+n,'exact',async()=>{const radio=page.locator('input[name="hid-outputs-mouse-radio"][value="'+mode+'"]');await page.locator('label[for="'+await radio.getAttribute('id')+'"]').click();await page.waitForFunction(m=>document.querySelector('input[name="hid-outputs-mouse-radio"]:checked')?.value===m,mode);let s;for(let i=0;i<30;i++){s=await state();if(s.mouse.outputs.active===mode)break;await pause(100);}assert.equal(s.mouse.outputs.active,mode);return {expected:[[],[],[]],mode};});
  await step('close-menu-'+n,'setup',async()=>{await page.locator('#system-dropdown > .menu-button').click();});
 }
 const workloadEnd=Date.now()+(workload==='workload'?120000:0);
 for(let n=0;n<4||Date.now()<workloadEnd||n%2===1;n++){
  if(workload==='workload')await step('workload-key-'+n,'exact',async()=>{await page.locator('#stream-window').focus();await page.keyboard.press('KeyA');return {expected:[[[[1,30,1]],[[1,30,0]]],[],[]]};});
  const mode=n%2?'usb':'usb_rel';await switchMode(mode,n);
  if(mode==='usb_rel'){
   await step('pointer-lock-'+n,'setup',async()=>{await page.locator('#stream-box').click();await page.waitForFunction(()=>document.pointerLockElement?.id==='stream-box');await page.evaluate(()=>{window.observedMoves=[];if(!window.movesObserved){document.addEventListener('mousemove',e=>window.observedMoves.push([e.movementX,e.movementY]),{capture:true});window.movesObserved=true;}});execFileSync('xdotool',['mousemove_relative','--','1','0']);await pause(250);return {pointerLock:true};});

   for(const [j,dx,dy] of [[0,8,0],[1,-8,0],[2,0,6],[3,0,-6],[4,5,-4]]){
    await step('relative-'+n+'-'+j,'relative',async()=>{await page.evaluate(()=>window.observedMoves=[]);execFileSync('xdotool',['mousemove_relative','--',String(dx),String(dy)]);await pause(150);const moves=await page.evaluate(()=>window.observedMoves);assert.deepEqual(moves.filter(p=>p.some(v=>v)),[[dx,dy]]);return {moves,requested:[dx,dy]};});
   }
   await step('relative-button-'+n,'exact',async()=>{await page.mouse.down();await pause(100);await page.mouse.up();return {expected:[[],[],[[[1,272,1]],[[1,272,0]]]]};});
  }else{
   await step('absolute-return-'+n,'absolute',()=>absoluteAt(n%4===1?.4:.6,n%4===1?.6:.4));
  }
 }
 await step('focus-keyboard','setup',async()=>{await page.locator('#stream-window').focus();});
 await step('browser-held-shift','exact',async()=>{await page.keyboard.down('ShiftLeft');return {expected:[[[[1,42,1]]],[],[]]};},{held:[[42],[],[]]});
 await step('browser-close-cleanup','exact',async()=>{await page.close();return {expected:[[[[1,42,0]]],[],[]]};});
 page=await ctx.newPage();await step('reopen','setup',async()=>{await kvm();});
 // An additional real upstream WebSocket exercises disconnect and logout races.
 async function openSocket(){await page.evaluate(()=>new Promise((resolve,reject)=>{window.testSocket=new WebSocket('wss://blikvm-v4.lab/api/ws?stream=false');testSocket.onopen=resolve;testSocket.onerror=reject;}));await pause(300);}
 async function wsSend(type,event){await page.evaluate(({type,event})=>testSocket.send(JSON.stringify({event_type:type,event})),{type,event});}
 await step('api-websocket-open','setup',openSocket);
 await step('websocket-held-shift','exact',async()=>{await wsSend('key',{key:'ShiftLeft',state:true});return {expected:[[[[1,42,1]]],[],[]]};},{held:[[42],[],[]]});
 await step('websocket-close-cleanup','exact',async()=>{await page.evaluate(()=>testSocket.close());return {expected:[[[[1,42,0]]],[],[]]};});
 await step('revocation-socket-open','setup',openSocket);
 await step('logout-held-input','exact',async()=>{await wsSend('key',{key:'ShiftLeft',state:true});await pause(100);await wsSend('mouse_button',{button:'left',state:true});return {expected:[[[[1,42,1]]],[[[1,272,1]]],[]]};},{held:[[42],[272],[]]});
 await step('logout-cleanup-and-stale-socket','exact',async()=>{await post('/auth/logout');await page.evaluate(()=>{try{testSocket.send(JSON.stringify({event_type:'key',event:{key:'KeyA',state:true}}));testSocket.send(new Uint8Array([1,1,75,101,121,65]));}catch{}});await page.waitForFunction(()=>testSocket.readyState===WebSocket.CLOSED);const staleSocket=await page.evaluate(()=>testSocket.readyState);const r=await ctx.request.post(base+'/api/hid/events/send_key?key=KeyA');assert([401,403].includes(r.status()));return {expected:[[[[1,42,0]]],[[[1,272,0]]],[]],staleHttp:r.status(),staleSocket};});
 await step('reauth','setup',async()=>{await login();await kvm();await page.locator('#stream-window').focus();});
 await step('restart-held-input','exact',async()=>{await page.keyboard.down('ShiftLeft');await post('/hid/events/send_mouse_button?button=left&state=true');return {expected:[[[[1,42,1]]],[[[1,272,1]]],[]]};},{held:[[42],[272],[]]});
 await step('kvmd-restart-cleanup','restart',async()=>{const statuses=[];for(let i=0;i<60;i++){const r=await ctx.request.get(base+'/api/auth/check');statuses.push(r.status());if([200,401,403].includes(r.status()))return {readiness:statuses};await pause(500);}throw Error('kvmd API did not recover: '+statuses);},{service:'kvmd'});
 await step('restart-reauth','setup',async()=>{await page.keyboard.up('ShiftLeft');await page.close();page=await ctx.newPage();await login();await kvm();await page.locator('#stream-window').focus();});
 await step('keyboard-after-restart','exact',async()=>{await page.keyboard.press('KeyA');return {expected:[[[[1,30,1]],[[1,30,0]]],[],[]]};});
 await step('nginx-restart','restart',async()=>({}),{service:'nginx'});
 await step('nginx-reconnect','setup',async()=>{await page.reload();await page.waitForFunction(()=>document.querySelector('#link-led')?.title==='Connected');});
 await step('video-motion','setup',async()=>{const hashes=[];for(let i=0;i<6;i++){const data=await page.evaluate(()=>{let im=document.querySelector('#stream-image'),c=document.createElement('canvas');c.width=im.naturalWidth;c.height=im.naturalHeight; c.getContext('2d').drawImage(im,0,0);return c.toDataURL();});hashes.push(crypto.createHash('sha256').update(data).digest('hex'));await pause(500);}assert(new Set(hashes).size>=4);return {hashes};});
 await page.screenshot({path:path.join(out,'browser.png')});
 await step('final-close','setup',async()=>{await ctx.close();});
 result.result='passed';
}catch(e){result.error=e.stack;}finally{if(browser)await browser.close();fs.writeFileSync(path.join(out,'browser-result.json'),JSON.stringify(result,null,2));}
process.exitCode=result.result==='passed'?0:1;
