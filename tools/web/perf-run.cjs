// Usage: node perf-run.cjs <package-dir> [http-port=8841] [cdp-port=9441] [seconds=15]
const { spawn, spawnSync } = require('child_process');
const fs = require('fs'), os = require('os'), path = require('path');
const pkg = process.argv[2], httpPort = process.argv[3] || '8841', cdpPort = process.argv[4] || '9441';
const seconds = Number(process.argv[5] || 15);
if (!pkg) throw new Error('package-dir obrigatorio');
const edge = 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe';
const profile = fs.mkdtempSync(path.join(os.tmpdir(), 'range-perf-edge-'));
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
const stop = child => { if (child && child.pid) spawnSync('taskkill', ['/PID', String(child.pid), '/T', '/F']); };
(async () => {
  const server = spawn('python', ['serve.py', httpPort], { cwd: pkg, stdio: 'ignore' });
  const browser = spawn(edge, ['--headless=new', '--remote-debugging-port=' + cdpPort, '--user-data-dir=' + profile,
    '--no-first-run', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist', 'about:blank'], { stdio: 'ignore' });
  try {
    let target;
    for (let i = 0; i < 40 && !target; ++i) { await sleep(250); try { target = await (await fetch('http://127.0.0.1:' + cdpPort + '/json/new?about:blank', { method: 'PUT' })).json(); } catch (_) {} }
    if (!target) throw new Error('Edge nao abriu CDP');
    const ws = new WebSocket(target.webSocketDebuggerUrl); await new Promise(resolve => ws.onopen = resolve);
    let id = 0; const pending = new Map(); ws.onmessage = e => { const m = JSON.parse(e.data); if (m.id) { pending.get(m.id)?.(m.result); pending.delete(m.id); } };
    const call = (method, params = {}) => new Promise(resolve => { pending.set(++id, resolve); ws.send(JSON.stringify({ id, method, params })); });
    const evaluate = async expression => (await call('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true })).result?.value;
    await call('Runtime.enable'); await call('Page.enable');
    await call('Page.navigate', { url: 'http://127.0.0.1:' + httpPort + '/?perf=1' });
    for (let i = 0; i < 120; ++i) { await sleep(250); if (await evaluate("document.getElementById('play') && !document.getElementById('play').disabled")) break; }
    await evaluate("document.getElementById('play').click()"); await sleep(seconds * 1000);
    const result = await evaluate('window.__rangePerf && window.__rangePerf()');
    console.log('[perf-run]', JSON.stringify(result));
    if (!result || result.count < 1) throw new Error('sonda nao recebeu frames');
    await call('Page.close'); ws.close(); process.exitCode = 0;
  } catch (error) { console.error('ERRO', error.message); process.exitCode = 1; }
  finally { stop(browser); stop(server); await sleep(250); fs.rmSync(profile, { recursive: true, force: true }); }
})();
