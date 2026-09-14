// Per-launch prospective contract and exact-UID gate for the frozen UI probes.
const fs=require('node:fs'), path=require('node:path'), crypto=require('node:crypto');
const cp=require('node:child_process'), assert=require('node:assert/strict');
const base='/var/lib/blikvm-p3-h5r1';
const c=JSON.parse(fs.readFileSync(base+'/input/contract.json'));
const f=JSON.parse(fs.readFileSync(base+'/input/functional/contract.json'));
const hash=p=>crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');
let iteration=0;
module.exports=function(out){
 const prefix=path.join(out,'launch-'+String(++iteration).padStart(3,'0'));
 assert.equal(process.getuid(),c.uid);assert.equal(process.getgid(),c.gid);assert.deepEqual(process.getgroups(),c.groups);
 assert.equal(process.env.HOME,c.home);assert.equal(process.cwd(),c.cwd);
 assert(!Object.hasOwn(process.env,'TMPDIR')&&!Object.hasOwn(process.env,'XDG_RUNTIME_DIR'));
 assert.equal(process.env.DEBUG,'pw:browser*');
 for(const [name,expected] of Object.entries(f.executables))assert.equal(hash(name),expected.sha256);
 assert.equal(hash(process.execPath),c.executables['/usr/bin/node'].sha256);
 assert.equal(hash(c.chromium),c.chromium_sha256);assert.equal(hash(c.playwright+'/package.json'),c.playwright_sha256);
 const observed=require(base+'/input/p3-h5r1-netns.cjs').observe();
 assert.equal(observed.netns,process.env.H5R1_HOST_NETNS);
 assert.deepEqual(observed.sockets,[]);
 const contract={phase:'before_launch',frozen_contract:c,functional_contract:f,
  contract_sha256:hash(base+'/input/contract.json'),functional_contract_sha256:hash(base+'/input/functional/contract.json'),
  uid:process.getuid(),gid:process.getgid(),groups:process.getgroups(),cwd:process.cwd(),
  node:process.execPath,node_version:process.version,node_sha256:hash(process.execPath),
  playwright_version:require(c.playwright+'/package.json').version,playwright_sha256:hash(c.playwright+'/package.json'),
  chromium_sha256:hash(c.chromium),full_environment:{...process.env},network:observed,
  launch_options:{headless:false},xvfb_arguments:c.xvfb_arguments};
 fs.writeFileSync(prefix+'-contract.json',JSON.stringify(contract,null,2));
 let raw;
 try{raw=cp.execFileSync('/usr/bin/python3',[base+'/input/p3-h5r1.py','worker'],
  {input:fs.readFileSync(process.env.P3_LAUNCH_REQUIREMENTS),encoding:'utf8',maxBuffer:64*1024*1024});}
 catch(e){if(e.stdout)fs.writeFileSync(prefix+'-audit.json',e.stdout);throw e;}
 fs.writeFileSync(prefix+'-audit.json',raw);
 const a=JSON.parse(raw);assert.equal(a.uid,c.uid);assert.equal(a.gid,c.gid);assert.deepEqual(a.groups,c.groups);
 assert(a.operations.length && a.operations.every(o=>o.passed));
};
