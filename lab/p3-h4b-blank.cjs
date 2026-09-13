#!/usr/bin/env node
// Diagnostic only. A reviewed complete contract and network-isolated external
// controller must precede execution; the currently recovered contracts block.
const fs = require('node:fs');
const crypto = require('node:crypto');
const path = require('node:path');
const contract = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
function requireCondition(condition, message) {
  if (!condition) throw new Error(message);
}
requireCondition(contract.exact_reproduction_ready === true, 'historical control is incomplete');
requireCondition(process.getuid() === 995 && process.getgid() === 983 &&
  JSON.stringify(process.getgroups()) === '[983]', 'unexpected browser identity');
requireCondition(process.env.DEBUG === 'pw:browser*', 'launch debug capture required');
requireCondition(JSON.stringify(fs.readdirSync('/sys/class/net').sort()) === '["lo"]',
  'external controller must isolate target network before launch');
const modulePath = contract.playwright_module.value;
requireCondition(path.isAbsolute(modulePath), 'exact absolute module path required');
const packageBytes = fs.readFileSync(path.join(modulePath, 'package.json'));
requireCondition(crypto.createHash('sha256').update(packageBytes).digest('hex') ===
  contract.playwright_package_sha256, 'Playwright package identity changed');
const {chromium} = require(modulePath);
const executable = chromium.executablePath();
requireCondition(executable === contract.chromium.path, 'Chromium path differs from contract');
requireCondition(crypto.createHash('sha256').update(fs.readFileSync(executable)).digest('hex') ===
  contract.chromium.sha256, 'Chromium bytes differ from contract');
const safeNames = ['HOME', 'TMPDIR', 'XDG_RUNTIME_DIR', 'DISPLAY', 'XAUTHORITY',
  'NODE_EXTRA_CA_CERTS', 'PLAYWRIGHT_BROWSERS_PATH', 'PLAYWRIGHT_HOST_PLATFORM_OVERRIDE', 'PATH'];
console.log(JSON.stringify({phase: 'before_launch', uid: process.getuid(), gid: process.getgid(),
  groups: process.getgroups(), cwd: process.cwd(), node: process.execPath, node_version: process.version,
  playwright_version: JSON.parse(packageBytes).version, executable,
  environment: Object.fromEntries(safeNames.map(k => [k, process.env[k] ?? null])),
  dbus_session_bus_address_present: Object.hasOwn(process.env, 'DBUS_SESSION_BUS_ADDRESS')}));
(async () => {
  let browser;
  let context;
  try {
    browser = await chromium.launch({headless:false});
    context = await browser.newContext();
    const page = await context.newPage();
    await page.goto('about:blank');
    requireCondition(page.url() === 'about:blank', 'unexpected page');
    await context.close();
    context = null;
    await browser.close();
    browser = null;
    console.log(JSON.stringify({result: 'MINIMAL_PROBE_PASS_PENDING_ARGV_REPLAY', qualification_credit: 0}));
  } catch (error) {
    console.error(String(error));
    process.exitCode = 1;
  } finally {
    if (context) await context.close().catch(() => {});
    if (browser) await browser.close().catch(() => {});
  }
})();
