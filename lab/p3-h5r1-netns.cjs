// Namespace-aware observation only. No Playwright or browser dependency.
const fs = require('node:fs');
const os = require('node:os');
const cp = require('node:child_process');
const assert = require('node:assert/strict');
function observe() {
  const raw = {};
  for (const [name, args] of Object.entries({link:['-j','link','show'], route:['-j','route','show'], route6:['-6','-j','route','show','table','all']})) {
    const p = cp.spawnSync('/usr/sbin/ip', args, {encoding:'utf8'});
    raw[name] = {args, status:p.status, stdout:p.stdout, stderr:p.stderr};
  }
  const sockets = [];
  for (const fd of fs.readdirSync('/proc/self/fd')) {
    try { const target=fs.readlinkSync('/proc/self/fd/'+fd); if(target.startsWith('socket:')) sockets.push({fd,target}); }
    catch(e) { if(e.code!=='ENOENT') throw e; }
  }
  let sysfs;
  try { sysfs=fs.readdirSync('/sys/class/net'); } catch(e) { sysfs={error:e.code}; }
  return {netns:fs.readlinkSync('/proc/self/ns/net'), uid:process.getuid(), gid:process.getgid(),
    groups:process.getgroups(), interfaces:os.networkInterfaces(), raw, sockets,
    sysfs_interfaces_observed:sysfs};
}
function validate(r, expected) {
  assert.notEqual(r.netns,expected.host_netns);
  assert.equal(r.netns,expected.netns);
  assert.equal(r.uid,expected.uid); assert.equal(r.gid,expected.gid); assert.deepEqual(r.groups,expected.groups);
  assert.deepEqual(Object.keys(r.interfaces),['lo']);
  assert(r.interfaces.lo.length>0 && r.interfaces.lo.every(a=>a.internal && (a.address==='::1'||a.address.startsWith('127.'))));
  for(const p of Object.values(r.raw)) assert.equal(p.status,0);
  assert.deepEqual(JSON.parse(r.raw.link.stdout).map(x=>x.ifname),['lo']);
  for(const k of ['route','route6']) assert(JSON.parse(r.raw[k].stdout).every(x=>x.dev==='lo'&&!x.gateway));
  assert.deepEqual(r.sockets,[]);
  // sysfs_interfaces_observed is deliberately never used in an assertion.
}
module.exports={observe,validate};
if(require.main===module) {
  const r=observe();
  console.log(JSON.stringify(r));
  validate(r,JSON.parse(process.env.H5R1_NETNS_EXPECTED));
}
