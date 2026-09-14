#!/usr/bin/env node
// Prospective H5R1 contract probe; the controller externally isolates networking.
const fs = require('node:fs');
const crypto = require('node:crypto');
const cp = require('node:child_process');
const path = require('node:path');
const assert = require('node:assert/strict');
const base = '/var/lib/blikvm-p3-h5r1';
const c = JSON.parse(fs.readFileSync(base+'/input/contract.json'));
const leaf = process.env.H5R1_LEAF;
const hash = p => crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');
assert.equal(process.getuid(), c.uid);
assert.equal(process.getgid(), c.gid);
assert.deepEqual(process.getgroups(), c.groups);
assert.equal(process.env.HOME, c.home);
assert.equal(process.cwd(),c.cwd);
assert(!Object.hasOwn(process.env, 'TMPDIR'));
assert(!Object.hasOwn(process.env, 'XDG_RUNTIME_DIR'));
assert.equal(process.env.DEBUG, 'pw:browser*');
const net = require('./p3-h5r1-netns.cjs');
const observation = net.observe();
fs.writeFileSync(path.join(leaf,'netns-after-drop.json'),JSON.stringify(observation,null,2));
net.validate(observation,JSON.parse(process.env.H5R1_NETNS_EXPECTED));
assert.equal(hash(process.execPath), c.executables['/usr/bin/node'].sha256);
assert.equal(hash(c.playwright+'/package.json'), c.playwright_sha256);
const {chromium} = require(c.playwright);
assert.equal(chromium.executablePath(), c.chromium);
assert.equal(hash(c.chromium), c.chromium_sha256);
const safe = ['DISPLAY', 'XAUTHORITY', 'HOME', 'TMPDIR', 'XDG_RUNTIME_DIR', 'PATH',
              'PLAYWRIGHT_BROWSERS_PATH', 'PLAYWRIGHT_HOST_PLATFORM_OVERRIDE', 'DEBUG'];
const provenance = {full_environment: {...process.env}, frozen_contract:c,phase: 'before_launch', uid: process.getuid(), gid: process.getgid(), groups: process.getgroups(),
  cwd: process.cwd(), node: process.execPath, node_version: process.version, node_sha256: hash(process.execPath),
  playwright: c.playwright, playwright_version: require(c.playwright+'/package.json').version,
  playwright_sha256: hash(c.playwright+'/package.json'), chromium: c.chromium, chromium_sha256: hash(c.chromium),
  environment: Object.fromEntries(safe.map(k=>[k, {present: Object.hasOwn(process.env,k), value: process.env[k]??null}])),
  dbus_session_bus_address_present: Object.hasOwn(process.env,'DBUS_SESSION_BUS_ADDRESS'),
  network_namespace: fs.readlinkSync('/proc/self/ns/net'), host_network_namespace: JSON.parse(process.env.H5R1_NETNS_EXPECTED).host_netns,
  interfaces: observation.interfaces, sysfs_interfaces_observed: observation.sysfs_interfaces_observed,
  contract_sha256: hash(base+'/input/contract.json'), launch_options: {headless:false}};
fs.writeFileSync(path.join(leaf,'launch-contract.json'), JSON.stringify(provenance,null,2));
(async()=>{
  let browser, context;
  const stages=[];
  try {
    // Global actual-UID syscall audit immediately before the sole launch API.
    const raw=cp.execFileSync('/usr/bin/python3',[base+'/input/p3-h5r1.py','worker'],
      {input:fs.readFileSync(process.env.H5R1_REQUIREMENTS),encoding:'utf8',maxBuffer:64*1024*1024});
    fs.writeFileSync(path.join(leaf,'launch-audit.json'),raw);
    const audit=JSON.parse(raw);
    assert.equal(audit.uid,c.uid); assert.equal(audit.gid,c.gid); assert.deepEqual(audit.groups,c.groups);
    assert(audit.operations.length>0 && audit.operations.every(o=>o.passed));
    browser=await chromium.launch({headless:false}); stages.push('launch');
    context=await browser.newContext(); stages.push('context');
    const page=await context.newPage(); stages.push('page');
    await page.goto('about:blank'); assert.equal(page.url(),'about:blank'); stages.push('about:blank');
    await context.close(); context=null; stages.push('context-close');
    await browser.close(); browser=null; stages.push('browser-close');
    fs.writeFileSync(path.join(leaf,'result.json'),JSON.stringify({result:'MINIMAL_BROWSER_PASS',stages}));
  } catch(e) {
    fs.writeFileSync(path.join(leaf,'result.json'),JSON.stringify({result:'FAILED',stages,error:String(e)}));
    console.error(e); process.exitCode=1;
  } finally {
    if(context) await context.close().catch(()=>{});
    if(browser) await browser.close().catch(()=>{});
  }
})();
