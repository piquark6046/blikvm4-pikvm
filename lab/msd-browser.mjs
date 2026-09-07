#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url);
const {chromium}=require(path.resolve('out/kvmd-web/browser/node_modules/playwright'));
const [privateDir,out]=process.argv.slice(2);
const credentials=JSON.parse(fs.readFileSync(path.join(privateDir,'credentials.json')));
const base='https://blikvm-v4.lab';
let browser,index=0;
const result={result:'failed',steps:[],errors:[]};
const pause=ms=>new Promise(r=>setTimeout(r,ms));
function publish(file,value){fs.writeFileSync(file+'.tmp',JSON.stringify(value));fs.renameSync(file+'.tmp',file);}
async function wait(file){const deadline=Date.now()+60000;while(!fs.existsSync(file)){assert(Date.now()<deadline,'host stage timeout');await pause(50);}}
async function stage(name,connected,action){
 const value=await action()||{};
 const stem=path.join(out,String(++index).padStart(3,'0'));
 publish(stem+'.ready',{name,connected,...value});await wait(stem+'.ok');
 const check=JSON.parse(fs.readFileSync(stem+'.ok'));assert.equal(check.result,'passed',JSON.stringify(check));
 result.steps.push({name,connected,...value});
}
try {
 browser=await chromium.launch({headless:false});result.version=browser.version();
 let ctx=await browser.newContext({ignoreHTTPSErrors:false,viewport:{width:1440,height:1000}});
 let page=await ctx.newPage();
 page.on('pageerror',e=>result.errors.push(e.message));page.on('dialog',d=>d.accept());
 async function login(){await page.goto(base+'/login/');await page.waitForFunction(()=>typeof document.querySelector('#login-button')?.onclick==='function');await page.locator('#user-input').fill(credentials.user);await page.locator('#passwd-input').fill(credentials.passwd);await page.locator('#login-button').click();await page.waitForURL(base+'/');}
 async function open(){await page.goto(base+'/kvm/');await page.waitForFunction(()=>document.querySelector('#link-led')?.title==='Connected');await page.waitForFunction(()=>document.querySelector('#stream-image')?.naturalWidth===1920);await page.locator('#msd-dropdown > .menu-button').click();}
 async function control(connected){await page.locator(connected?'#msd-connect-button':'#msd-disconnect-button').click();await page.waitForFunction(c=>{let e=document.querySelector(c?'#msd-disconnect-button':'#msd-connect-button');return e&&!e.disabled&&!e.classList.contains('hidden');},connected);}
 await stage('normal-login',true,async()=>{await login();await open();});
 await stage('excluded-controls',true,async()=>{
  for(const id of ['msd-rw-switch','msd-select-new-button','msd-upload-new-button','msd-remove-button','msd-download-button','msd-reset-button']){
   assert(await page.locator('#'+id).isDisabled(),id+' enabled');assert(!(await page.locator('#'+id).isVisible()),id+' visible');
  }
  await page.screenshot({path:path.join(out,'connected.png')});
 });
 await stage('ui-eject',false,()=>control(false));
 await stage('ui-select',false,async()=>{
  await page.locator('#msd-image-selector').selectOption('');
  await pause(300);
  await page.locator('#msd-image-selector').selectOption('g4-storage.img');
  await page.waitForFunction(()=>!document.querySelector('#msd-connect-button').disabled);
  assert.equal(await page.locator('#msd-image-selector').inputValue(),'g4-storage.img');
 });
 await stage('ui-connect',true,()=>control(true));
 await stage('ui-second-eject',false,()=>control(false));
 await stage('ui-reconnect',true,()=>control(true));
 await stage('logout-stale-websocket',true,async()=>{
  await page.evaluate(async()=>{
   window.msdStale=new WebSocket('wss://blikvm-v4.lab/api/ws?stream=false');
   await new Promise((res,rej)=>{window.msdStale.onopen=res;window.msdStale.onerror=rej;});
  });
  // Use the normal UI logout. Retain a same-origin helper page to attempt the stale socket.
  const stalePage=await ctx.newPage();await stalePage.goto(base+'/');
  await stalePage.evaluate(async()=>{
   window.msdStale=new WebSocket('wss://blikvm-v4.lab/api/ws?stream=false');
   await new Promise((res,rej)=>{window.msdStale.onopen=res;window.msdStale.onerror=rej;});
  });
  await page.goto(base+'/');
  await page.locator('#logout-button').click();
  await pause(500);
  const state=await stalePage.evaluate(async()=>{
   if(window.msdStale.readyState===WebSocket.OPEN){
    window.msdStale.send(JSON.stringify({event_type:'msd_set_connected',event:{connected:false}}));
    window.msdStale.send(JSON.stringify({event_type:'msd',event:{connected:false,rw:true}}));
   }
   const deadline=Date.now()+5000;
   while(window.msdStale.readyState!==WebSocket.CLOSED&&Date.now()<deadline)await new Promise(r=>setTimeout(r,50));
   return window.msdStale.readyState;
  });
  assert.equal(state,3);await stalePage.close();
  const denied=await ctx.request.post(base+'/api/msd/set_connected?connected=false');assert([401,403].includes(denied.status()));
  return {stale_socket_state:state,loggedout_status:denied.status(),reauth:true};
 });
 await stage('normal-relogin',true,async()=>{await login();await open();});
 await stage('browser-close',true,async()=>{await browser.close();return {browser_process_closed:true};});
 browser=await chromium.launch({headless:false});
 ctx=await browser.newContext({ignoreHTTPSErrors:false,viewport:{width:1440,height:1000}});
 page=await ctx.newPage();page.on('pageerror',e=>result.errors.push(e.message));page.on('dialog',d=>d.accept());
 await stage('browser-reopen',true,async()=>{await login();await open();});
 assert.deepEqual(result.errors,[]);
 result.result='passed';
} catch(e){result.error=String(e);}
finally {if(browser)await browser.close();fs.writeFileSync(path.join(out,'browser-result.json'),JSON.stringify(result,null,2));}
process.exit(result.result==='passed'?0:1);
