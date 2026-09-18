// Verificacao automatizada (sem julgamento visual) de um pacote Web gerado por package-web.py.
// Abre <url>?debug=1 num Chrome com CDP em tempo real, clica em "Jogar", envia uma seta e
// imprime o log do runtime. Sai com codigo != 0 se houver erro visivel, aborto ou excecao.
//
// Uso: node tools/web/verify-package.cjs http://127.0.0.1:8791/ [porta-cdp=9333] [segundos=25]
// Requer Chrome ja aberto com --remote-debugging-port=<porta-cdp> (ver docs/web-deploy.md).
const url = process.argv[2];
const port = process.argv[3] || '9333';
const seconds = Number(process.argv[4] || 25);
if (!url) { console.error('uso: verify-package.cjs <url> [porta-cdp] [segundos]'); process.exit(2); }

(async () => {
  const target = await (await fetch(`http://127.0.0.1:${port}/json/new?about:blank`, { method: 'PUT' })).json();
  const ws = new WebSocket(target.webSocketDebuggerUrl);
  await new Promise(r => (ws.onopen = r));
  let id = 0; const pending = new Map(); const logs = []; let bad = false;
  ws.onmessage = e => {
    const m = JSON.parse(e.data);
    if (m.id) { pending.get(m.id)?.(m.result); pending.delete(m.id); }
    else if (m.method === 'Runtime.consoleAPICalled') logs.push('[console] ' + m.params.args.map(a => a.value ?? a.description).join(' '));
    else if (m.method === 'Runtime.exceptionThrown') { bad = true; logs.push('[exception] ' + JSON.stringify(m.params.exceptionDetails.text)); }
  };
  const call = (method, params = {}) => new Promise(r => { pending.set(++id, r); ws.send(JSON.stringify({ id, method, params })); });
  const evalJs = async expr => (await call('Runtime.evaluate', { expression: expr, returnByValue: true })).result?.value;
  const sleep = ms => new Promise(r => setTimeout(r, ms));

  await call('Runtime.enable'); await call('Page.enable');
  await call('Network.enable'); await call('Network.setCacheDisabled', { cacheDisabled: true });
  await call('Page.navigate', { url: url + (url.includes('?') ? '&' : '?') + 'debug=1' });

  // Espera o botao Jogar liberar (runtime + dados carregados) ou erro visivel.
  let state = '';
  for (let i = 0; i < seconds * 2; i++) {
    await sleep(500);
    state = await evalJs(`(function(){var b=document.getElementById('play'),e=document.getElementById('error');
      if(e&&!e.hidden)return 'error';return b&&!b.disabled?'ready':'loading';})()`);
    if (state !== 'loading') break;
  }
  if (state === 'ready') {
    await evalJs(`document.getElementById('play').click()`);
    await sleep(3000);
    for (const type of ['keyDown', 'keyUp']) {
      await call('Input.dispatchKeyEvent', { type, key: 'ArrowRight', code: 'ArrowRight', windowsVirtualKeyCode: 39, nativeVirtualKeyCode: 39 });
      await sleep(300);
    }
    await sleep(2000);
  }
  const runtimeLog = await evalJs(`document.getElementById('log').textContent`);
  const errText = await evalJs(`document.getElementById('error').textContent`);
  console.log('estado:', state);
  console.log('--- log do runtime (ate 3000 chars) ---\n' + (runtimeLog || '').slice(0, 3000));
  if (errText) console.log('--- erro visivel ---\n' + errText);
  if (logs.length) console.log('--- console/excecoes ---\n' + logs.slice(0, 40).join('\n'));
  if (/\[ABORT\]|Aborted|alignment fault|segmentation/i.test(runtimeLog || '')) bad = true;

  await fetch(`http://127.0.0.1:${port}/json/close/${target.id}`);
  // Sem process.exit(): no Node 24 no Windows ele dispara um assert do libuv com o WebSocket aberto.
  // Fecha o socket, espera o onclose e deixa o processo terminar sozinho.
  process.exitCode = state === 'ready' && !bad ? 0 : 1;
  await new Promise(r => { ws.onclose = r; ws.close(); });
})();
