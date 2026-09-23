// Roda o pacote Web da sonda R3 (audio invalido) e exige '[r3] TODOS' sem abort num Edge headless isolado.
// Uso: node claude_m3_resize.cjs <pasta-do-pacote> [porta-http=8811] [porta-cdp=9411] [segundos=60]
// Sobe python serve.py e o Edge (perfil temporario) como filhos e encerra so esses PIDs. Imprime as linhas
// "[m3r]", "[web-filter]" e avisos/erros do console e um resumo com veredito.
const { spawn, spawnSync } = require('child_process');
const fs = require('fs'), os = require('os'), path = require('path');
const pkg = process.argv[2];
const httpPort = process.argv[3] || '8831', cdpPort = process.argv[4] || '9431';
const seconds = Number(process.argv[5] || 60);
const edge = 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe';
const prof = fs.mkdtempSync(path.join(os.tmpdir(), 'edge-r3-'));
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
      else if (m.method === 'Runtime.exceptionThrown') logs.push('[exception] ' + JSON.stringify(m.params.exceptionDetails.text) + ' ' + (m.params.exceptionDetails.exception?.description || m.params.exceptionDetails.exception?.value || ''));
    };
    const call = (method, params = {}) => new Promise(r => { pending.set(++id, r); ws.send(JSON.stringify({ id, method, params })); });
    const evalJs = async expr => (await call('Runtime.evaluate', { expression: expr, returnByValue: true })).result?.value;
    await call('Runtime.enable'); await call('Page.enable');
    await call('Page.addScriptToEvaluateOnNewDocument', { source: 'window.RAS_2DFILTER_DEBUG = true;' });
    await call('Page.navigate', { url: `http://127.0.0.1:${httpPort}/?debug=1` });
    let state = 'loading';
    for (let i = 0; i < 120 && state === 'loading'; i++) {
      await sleep(500);
      state = await evalJs(`(function(){var b=document.getElementById('play'),e=document.getElementById('error');
        if(e&&!e.hidden)return 'error';return b&&!b.disabled?'ready':'loading';})()`);
    }
    if (state === 'ready') {
      await evalJs(`document.getElementById('play').click()`);
      for (let i = 0; i < seconds * 2; i++) { await sleep(500); if (logs.some(l => l.includes('[r3] TODOS')) ) break; }
      await sleep(1500);
    }
    const all = logs.join('\n');
    fs.writeFileSync(path.join(os.tmpdir(), 'claude-r3-console.log'), all);
    const ok = logs.some(l => l.includes('[r3] TODOS'));
    console.log('estado:', state, '| linhas:', logs.length, '| [r3] TODOS:', ok);
    console.log(logs.filter(l => /\[r3\]|\[aud\]|Aborted|segmentation|\[exception\]/.test(l)).join('\n'));
    code = (state === 'ready' && ok) ? 0 : 1;
    await call('Page.close').catch(() => {});
    try { ws.close(); } catch (e) {}
  } catch (e) { console.error('ERRO', e); }
  kill(br); kill(srv);
  await sleep(1000);
  try { fs.rmSync(prof, { recursive: true, force: true }); } catch (e) {}
  process.exitCode = code;
})();
