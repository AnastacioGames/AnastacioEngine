// Roda o pacote Web do teste M3 (bloom + resize + resolucao dinamica) num Edge headless isolado.
// Uso: node claude_m3_resize.cjs <pasta-do-pacote> [porta-http=8811] [porta-cdp=9411] [segundos=60]
// Sobe python serve.py e o Edge (perfil temporario) como filhos e encerra so esses PIDs. Imprime as linhas
// "[m3r]", "[web-filter]" e avisos/erros do console e um resumo com veredito.
const { spawn, spawnSync } = require('child_process');
const fs = require('fs'), os = require('os'), path = require('path');
const pkg = process.argv[2];
const httpPort = process.argv[3] || '8811', cdpPort = process.argv[4] || '9411';
const seconds = Number(process.argv[5] || 60);
const edge = 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe';
const prof = fs.mkdtempSync(path.join(os.tmpdir(), 'edge-m3-'));
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
    await call('Page.navigate', { url: `http://127.0.0.1:${httpPort}/?debug=1` });
    let state = 'loading';
    for (let i = 0; i < 120 && state === 'loading'; i++) {
      await sleep(500);
      state = await evalJs(`(function(){var b=document.getElementById('play'),e=document.getElementById('error');
        if(e&&!e.hidden)return 'error';return b&&!b.disabled?'ready':'loading';})()`);
    }
    if (state === 'ready') {
      await evalJs(`document.getElementById('play').click()`);
      for (let i = 0; i < seconds * 2; i++) { await sleep(500); if (logs.some(l => l.includes('[m3r] FASE FIM')) ) break; }
      await sleep(1500);
    }
    const all = logs.join('\n');
    fs.writeFileSync(path.join(os.tmpdir(), 'claude-m3-console.log'), all);
    const filt = logs.filter(l => l.includes('[web-filter]'));
    console.log('estado:', state, '| linhas totais:', logs.length, '| [web-filter]:', filt.length);
    console.log(logs.filter(l => /\[m3r\]/.test(l)).join('\n'));
    // Resumo: por fase, tamanhos de offscreen distintos e erros GL.
    let fase = 'antes', porFase = {};
    for (const l of logs) {
      const m = l.match(/\[m3r\] FASE (\S+)/); if (m) { fase = m[1]; continue; }
      const f = l.match(/name=(\S+).*offScreen=(\d).*offScreenSize=(\d+x\d+) glError=(0x[0-9a-f]+)/);
      if (f) { (porFase[fase] ??= { sizes: new Set(), err: new Set(), n: 0 }); const p = porFase[fase]; p.n++; if (f[2] === '1') p.sizes.add(f[1] + ':' + f[3]); p.err.add(f[4]); }
    }
    for (const [k, v] of Object.entries(porFase)) console.log(k.padEnd(18), 'n=' + v.n, 'glError=' + [...v.err].join(','), 'offscreens=' + [...v.sizes].join(' '));
    const warn = logs.filter(l => /dynamic resolution|GL_INVALID|WebGL:|GL ERROR|Aborted|EXCECAO|\[exception\]/i.test(l));
    console.log('--- avisos/erros (ate 20) ---\n' + warn.slice(0, 20).join('\n'));
    console.log('log completo em', path.join(os.tmpdir(), 'claude-m3-console.log'));
    code = state === 'ready' ? 0 : 1;
    await call('Page.close').catch(() => {});
    try { ws.close(); } catch (e) {}
  } catch (e) { console.error('ERRO', e); }
  kill(br); kill(srv);
  await sleep(1000);
  try { fs.rmSync(prof, { recursive: true, force: true }); } catch (e) {}
  process.exitCode = code;
})();
