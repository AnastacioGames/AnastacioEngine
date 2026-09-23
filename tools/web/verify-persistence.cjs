// Smoke test de persistencia de saves (IDBFS em /saves) de um pacote Web. Sem julgamento visual.
// Grava um token em /saves, faz syncfs(false), recarrega a pagina (novo runtime) e confere que o
// arquivo voltou do IndexedDB. Limpa o arquivo no fim. Exercita a camada IDBFS, nao o
// saveGlobalDict do Python (esse caminho so acrescenta o syncfs(false) logo apos a escrita).
//
// Uso: node tools/web/verify-persistence.cjs http://127.0.0.1:8791/ [porta-cdp=9333] [segundos=25]
// Requer Chrome ja aberto com --remote-debugging-port=<porta-cdp> e o runtime com Module.FS exposto.
const url = process.argv[2];
const port = process.argv[3] || '9333';
const seconds = Number(process.argv[4] || 25);
if (!url) { console.error('uso: verify-persistence.cjs <url> [porta-cdp] [segundos]'); process.exit(2); }

(async () => {
  const target = await (await fetch(`http://127.0.0.1:${port}/json/new?about:blank`, { method: 'PUT' })).json();
  const ws = new WebSocket(target.webSocketDebuggerUrl);
  await new Promise(r => (ws.onopen = r));
  let id = 0; const pending = new Map();
  ws.onmessage = e => { const m = JSON.parse(e.data); if (m.id) { pending.get(m.id)?.(m.result); pending.delete(m.id); } };
  const call = (method, params = {}) => new Promise(r => { pending.set(++id, r); ws.send(JSON.stringify({ id, method, params })); });
  const evalJs = async expr => (await call('Runtime.evaluate', { expression: expr, returnByValue: true, awaitPromise: true })).result?.value;
  const sleep = ms => new Promise(r => setTimeout(r, ms));

  const load = async () => {
    await call('Page.navigate', { url });
    for (let i = 0; i < seconds * 2; i++) {
      await sleep(500);
      const s = await evalJs(`(function(){var b=document.getElementById('play'),e=document.getElementById('error');
        if(e&&!e.hidden)return 'error';return b&&!b.disabled?'ready':'loading';})()`);
      if (s !== 'loading') return s;
    }
    return 'loading';
  };
  const sync = `new Promise(r => Module.FS.syncfs(false, e => r(e ? String(e) : 'ok')))`;
  const path = '/saves/persist-smoke.save';
  const token = 'tok-' + Date.now();
  const results = [];
  const check = (name, ok, extra = '') => { results.push(ok); console.log((ok ? 'OK   ' : 'FALHA') + ' ' + name + (extra ? ' - ' + extra : '')); };

  await call('Runtime.enable'); await call('Page.enable');
  await call('Network.enable'); await call('Network.setCacheDisabled', { cacheDisabled: true });

  const s1 = await load();
  check('sessao 1 pronta', s1 === 'ready', s1);
  if (s1 === 'ready') {
    check('Module.FS exposto', await evalJs(`typeof Module.FS === 'object'`) === true);
    check('/saves montado como IDBFS', await evalJs(`Module.FS.analyzePath('/saves').exists`) === true);
    check('estado inicial sem token anterior', await evalJs(`!Module.FS.analyzePath('${path}').exists`) === true,
      'sobra de execucao anterior se falhar');
    await evalJs(`Module.FS.writeFile('${path}', '${token}')`);
    check('syncfs(false) gravou no IndexedDB', await evalJs(sync) === 'ok');
  }

  const s2 = await load(); // novo runtime: o pre-js refaz o mount e o syncfs(true) inicial
  check('sessao 2 pronta', s2 === 'ready', s2);
  if (s2 === 'ready') {
    const back = await evalJs(`Module.FS.analyzePath('${path}').exists ? Module.FS.readFile('${path}', {encoding:'utf8'}) : null`);
    check('save voltou do IndexedDB apos recarregar', back === token, `esperado ${token}, veio ${back}`);
    await evalJs(`Module.FS.unlink('${path}')`);
    check('limpeza sincronizada', await evalJs(sync) === 'ok');
  }

  await fetch(`http://127.0.0.1:${port}/json/close/${target.id}`);
  process.exitCode = results.length && results.every(Boolean) ? 0 : 1;
  await new Promise(r => { ws.onclose = r; ws.close(); });
})();
