// Teste ponta a ponta de Range.logic.saveGlobalDict/loadGlobalDict num pacote Web feito com
// tools/create_web_save_scene.py. Sem julgamento visual: le o console do runtime.
// Sessao 1: o jogo grava o dict e imprime "[web-save] SAVED". Sessao 2 (pagina recarregada):
// o jogo le do IndexedDB e imprime "[web-save] LOADED". Limpa /saves/ci.save no fim.
//
// Uso: node tools/web/verify-save.cjs http://127.0.0.1:8791/ [porta-cdp=9333] [segundos=25]
const url = process.argv[2];
const port = process.argv[3] || '9333';
const seconds = Number(process.argv[4] || 25);
if (!url) { console.error('uso: verify-save.cjs <url> [porta-cdp] [segundos]'); process.exit(2); }

(async () => {
  const target = await (await fetch(`http://127.0.0.1:${port}/json/new?about:blank`, { method: 'PUT' })).json();
  const ws = new WebSocket(target.webSocketDebuggerUrl);
  await new Promise(r => (ws.onopen = r));
  let id = 0; const pending = new Map(); let log = [];
  ws.onmessage = e => {
    const m = JSON.parse(e.data);
    if (m.id) { pending.get(m.id)?.(m.result); pending.delete(m.id); }
    else if (m.method === 'Runtime.consoleAPICalled') log.push(m.params.args.map(a => a.value ?? a.description ?? '').join(' '));
  };
  const call = (method, params = {}) => new Promise(r => { pending.set(++id, r); ws.send(JSON.stringify({ id, method, params })); });
  const evalJs = async expr => (await call('Runtime.evaluate', { expression: expr, returnByValue: true, awaitPromise: true })).result?.value;
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const results = [];
  const check = (name, ok, extra = '') => { results.push(ok); console.log((ok ? 'OK   ' : 'FALHA') + ' ' + name + (extra ? ' - ' + extra : '')); };
  const sync = `new Promise(r => Module.FS.syncfs(false, e => r(e ? String(e) : 'ok')))`;
  const path = '/saves/ci.save';

  // Carrega, espera o botao, opcionalmente clica em Jogar e espera o marcador (SAVED/LOADED).
  const session = async (play) => {
    log = [];
    await call('Page.navigate', { url });
    let state = 'loading';
    for (let i = 0; i < seconds * 2 && state === 'loading'; i++) {
      await sleep(500);
      state = await evalJs(`(function(){var b=document.getElementById('play'),e=document.getElementById('error');
        if(e&&!e.hidden)return 'error';return b&&!b.disabled?'ready':'loading';})()`);
    }
    if (state !== 'ready' || !play) return { state, marker: null };
    await evalJs(`document.getElementById('play').click()`);
    for (let i = 0; i < seconds * 2; i++) {
      await sleep(500);
      const m = log.find(l => /\[web-save\] (SAVED|LOADED)/.test(l));
      if (m) return { state, marker: /SAVED/.test(m) ? 'SAVED' : 'LOADED' };
    }
    return { state, marker: null };
  };

  await call('Runtime.enable'); await call('Page.enable');
  await call('Network.enable'); await call('Network.setCacheDisabled', { cacheDisabled: true });

  // Sessao 0: limpa sobra de execucao anterior.
  const s0 = await session(false);
  if (s0.state === 'ready') {
    await evalJs(`Module.FS.analyzePath('${path}').exists && Module.FS.unlink('${path}')`);
    await evalJs(sync);
  }
  const s1 = await session(true);
  check('sessao 1: jogo gravou com saveGlobalDict', s1.marker === 'SAVED', `estado=${s1.state} marcador=${s1.marker}`);
  if (s1.marker === 'SAVED') {
    await sleep(1500); // syncfs(false) do runtime e assincrono
    check('arquivo /saves/ci.save existe', await evalJs(`Module.FS.analyzePath('${path}').exists`) === true);
  }
  const s2 = await session(true);
  check('sessao 2 (recarregada): loadGlobalDict devolveu o dict', s2.marker === 'LOADED', `estado=${s2.state} marcador=${s2.marker}`);
  if (s2.state === 'ready') {
    await evalJs(`Module.FS.analyzePath('${path}').exists && Module.FS.unlink('${path}')`);
    check('limpeza sincronizada', await evalJs(sync) === 'ok');
  }

  await fetch(`http://127.0.0.1:${port}/json/close/${target.id}`);
  process.exitCode = results.length && results.every(Boolean) ? 0 : 1;
  await new Promise(r => { ws.onclose = r; ws.close(); });
})();
