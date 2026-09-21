// Roda um pacote Web com falha de shader injetada num Edge headless isolado e imprime o relatorio de pre-voo.
// Uso: node claude_m1c_diag.cjs <pasta-do-pacote> [porta-http=8821] [porta-cdp=9421] [segundos=25]
// Sobe python serve.py e o Edge (perfil temporario) como filhos e encerra so esses PIDs. Grava o relatorio em
// <tmp>/claude-m1c-preflight.json e imprime diagnostics[]/shader_errors[] (stage, operation, material/origin).
const { spawn, spawnSync } = require('child_process');
const fs = require('fs'), os = require('os'), path = require('path');
const pkg = process.argv[2];
const httpPort = process.argv[3] || '8821', cdpPort = process.argv[4] || '9421';
const seconds = Number(process.argv[5] || 25);
const edge = 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe';
const prof = fs.mkdtempSync(path.join(os.tmpdir(), 'edge-m1c-'));
const sleep = ms => new Promise(r => setTimeout(r, ms));
const kill = c => { try { spawnSync('taskkill', ['/PID', String(c.pid), '/T', '/F']); } catch (e) {} };

(async () => {
  const srv = spawn('python', ['serve.py', httpPort], { cwd: pkg, stdio: 'ignore' });
  const br = spawn(edge, ['--headless=new', '--remote-debugging-port=' + cdpPort, '--user-data-dir=' + prof,
    '--no-first-run', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist',
    '--window-size=960,540', 'about:blank'], { stdio: 'ignore' });
  let code = 1;
  try {
    let target;
    for (let i = 0; i < 40 && !target; i++) {
      await sleep(500);
      try { target = await (await fetch(`http://127.0.0.1:${cdpPort}/json/new?about:blank`, { method: 'PUT' })).json(); } catch (e) {}
    }
    if (!target) throw new Error('Edge nao abriu a porta CDP');
    const ws = new WebSocket(target.webSocketDebuggerUrl);
    await new Promise(r => (ws.onopen = r));
    let id = 0; const pending = new Map(); const logs = [];
    ws.onmessage = e => {
      const m = JSON.parse(e.data);
      if (m.id) { pending.get(m.id)?.(m.result); pending.delete(m.id); }
      else if (m.method === 'Runtime.consoleAPICalled') logs.push(m.params.args.map(a => a.value ?? a.description ?? '').join(' '));
      else if (m.method === 'Runtime.exceptionThrown') logs.push('[exception] ' + JSON.stringify(m.params.exceptionDetails.text));
    };
    const call = (method, params = {}) => new Promise(r => { pending.set(++id, r); ws.send(JSON.stringify({ id, method, params })); });
    const evalJs = async expr => (await call('Runtime.evaluate', { expression: expr, returnByValue: true })).result?.value;
    await call('Runtime.enable'); await call('Page.enable');
    await call('Page.addScriptToEvaluateOnNewDocument', { source: 'window.RAS_2DFILTER_DEBUG = true;' });
    await call('Page.navigate', { url: `http://127.0.0.1:${httpPort}/?debug=1&preflight=1` });
    let state = 'loading';
    for (let i = 0; i < 120 && state === 'loading'; i++) {
      await sleep(500);
      state = await evalJs(`(function(){var b=document.getElementById('play'),e=document.getElementById('error');
        if(e&&!e.hidden)return 'error';return b&&!b.disabled?'ready':'loading';})()`);
    }
    if (state === 'ready') {
      await evalJs(`document.getElementById('play').click()`);
      await sleep(seconds * 1000);
    }
    const r = await call('Runtime.evaluate', { expression: 'window.rangePreflight()', awaitPromise: true, returnByValue: true });
    const rep = r.result?.value ?? null;
    fs.writeFileSync(path.join(os.tmpdir(), 'claude-m1c-preflight.json'), JSON.stringify(rep, null, 2));
    console.log('estado:', state);
    console.log(logs.filter(l => /shader_quebrado|Aborted|\[exception\]/.test(l)).join('\n'));
    console.log('diagnostics:', JSON.stringify(rep?.diagnostics ?? null, null, 1).slice(0, 3000));
    console.log('shader_errors:', JSON.stringify(rep?.shader_errors ?? null, null, 1).slice(0, 3000));
    code = state === 'ready' ? 0 : 1;
    await call('Page.close').catch(() => {});
    try { ws.close(); } catch (e) {}
  } catch (e) { console.error('ERRO', e); }
  kill(br); kill(srv);
  await sleep(1000);
  try { fs.rmSync(prof, { recursive: true, force: true }); } catch (e) {}
  process.exitCode = code;
})();
