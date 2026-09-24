// Verificacao automatizada do controle na tela como gamepad 0 (Module.rangePad -> DEV_Joystick -> Python e
// sensor Joystick), sem controle fisico. Usa a cena de tools/tests/web_profile/make_pad_project.py, que imprime
// "[pad] ..." a cada 30 quadros e "[pad] sensor A down/up" pelo logic brick.
//
// Uso: node tools/web/verify-pad.cjs http://127.0.0.1:8792/ [porta-cdp=9333]
// Requer Chrome/Edge aberto com --remote-debugging-port=<porta-cdp> (ver docs/web-deploy.md).
// Escreve Module.rangePad direto (sem overlay): prova a ponte JS -> wasm, nao o toque (ver verify-touch.cjs).
// Rodar sem controle fisico ligado: com ele, joysticks[0] existe e o nome e o do controle.
const url = process.argv[2];
const port = process.argv[3] || '9333';
if (!url) { console.error('uso: verify-pad.cjs <url> [porta-cdp]'); process.exit(2); }

(async () => {
  const target = await (await fetch(`http://127.0.0.1:${port}/json/new?about:blank`, { method: 'PUT' })).json();
  const ws = new WebSocket(target.webSocketDebuggerUrl);
  await new Promise(r => (ws.onopen = r));
  let id = 0; const pending = new Map(); const errors = [];
  ws.onmessage = e => {
    const m = JSON.parse(e.data);
    if (m.id) { pending.get(m.id)?.(m.error ? { error: m.error } : m.result); pending.delete(m.id); }
    else if (m.method === 'Runtime.exceptionThrown') errors.push(JSON.stringify(m.params.exceptionDetails.text));
  };
  const call = (method, params = {}) => new Promise(r => { pending.set(++id, r); ws.send(JSON.stringify({ id, method, params })); });
  const evalJs = async expr => (await call('Runtime.evaluate', { expression: expr, returnByValue: true })).result?.value;
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const logText = async () => (await evalJs(`document.getElementById('log').textContent`)) || '';
  const lastPad = async from => {
    const lines = (await logText()).slice(from).split('\n').filter(l => /\[pad\] connected=/.test(l));
    return lines.length ? lines[lines.length - 1] : '';
  };
  const setPad = (active, axes, buttons) =>
    evalJs(`(function(){var p=Module.rangePad;p.active=${active};p.axes=${JSON.stringify(axes)};p.buttons=${buttons};return true;})()`);
  const results = [];
  const check = (name, ok, detail) => { results.push(ok); console.log(`${ok ? 'OK  ' : 'FALHA'} ${name}: ${detail}`); };

  await call('Runtime.enable'); await call('Page.enable');
  await call('Network.enable'); await call('Network.setCacheDisabled', { cacheDisabled: true });
  await call('Page.navigate', { url: url + (url.includes('?') ? '&' : '?') + 'debug=1' });

  let state = 'loading';
  for (let i = 0; i < 60 && state === 'loading'; i++) {
    await sleep(500);
    state = await evalJs(`(function(){var b=document.getElementById('play'),e=document.getElementById('error');
      if(e&&!e.hidden)return 'error';return b&&!b.disabled?'ready':'loading';})()`);
  }
  if (state !== 'ready') {
    console.log('pagina nao ficou pronta:', state, await evalJs(`document.getElementById('error').textContent`));
    process.exitCode = 1;
    return;
  }
  await evalJs(`document.getElementById('play').click()`);

  // 1. Pagina sem controle na tela: nenhum gamepad.
  await sleep(3000);
  let line = await lastPad(0);
  check('sem pad: joysticks[0] vazio', /connected=False/.test(line), line || '(nenhuma linha [pad])');

  // 2. Pad ativo, stick esquerdo a direita e para cima (LX=1, LY=-0.5), gatilho direito 0.25.
  await setPad(true, [1, -0.5, 0, 0, 0, 0.25], 0);
  let mark = (await logText()).length;
  await sleep(2000);
  line = await lastPad(mark);
  const m = /name=(.+?) axes=\[([^\]]*)\]/.exec(line);
  const axes = m ? m[2].split(',').map(Number) : [];
  check('pad ativo vira joysticks[0]', /connected=True name=Range Virtual Pad/.test(line), line || '(nenhuma linha [pad])');
  // axisValues do Python ja vem normalizado (-1..1) a partir da faixa do SDL.
  check('eixos chegam ao Python (LX 1, LY -0.5, RT 0.25)',
        axes[0] === 1 && axes[1] === -0.5 && axes[5] === 0.25, m ? `[${m[2]}]` : '-');

  // 3. Botao A (bit 0): Python ve activeButtons e o sensor Joystick dispara down/up.
  mark = (await logText()).length;
  await setPad(true, [0, 0, 0, 0, 0, 0], 1);
  await sleep(1200);
  line = await lastPad(mark);
  const log3 = (await logText()).slice(mark);
  check('botao A em activeButtons', /buttons=\[0\]/.test(line), line || '-');
  check('sensor Joystick A down', /\[pad\] sensor A down/.test(log3), (log3.match(/\[pad\] sensor A \w+/) || ['(sem evento)'])[0]);
  mark = (await logText()).length;
  await setPad(true, [0, 0, 0, 0, 0, 0], 0);
  await sleep(1200);
  check('sensor Joystick A up ao soltar', /\[pad\] sensor A up/.test((await logText()).slice(mark)), '-');

  // 4. Pad desligado: o gamepad virtual some.
  await setPad(false, [0, 0, 0, 0, 0, 0], 0);
  mark = (await logText()).length;
  await sleep(2000);
  line = await lastPad(mark);
  check('pad inativo: joysticks[0] vazio de novo', /connected=False/.test(line), line || '-');

  if (errors.length) console.log('--- excecoes JS ---\n' + errors.join('\n'));
  await fetch(`http://127.0.0.1:${port}/json/close/${target.id}`);
  process.exitCode = results.every(Boolean) && !errors.length ? 0 : 1;
  console.log(process.exitCode === 0 ? 'PAD: PASS' : 'PAD: FAIL');
  // Sem process.exit(): no Node 24 no Windows ele dispara um assert do libuv com o WebSocket aberto.
  await new Promise(r => { ws.onclose = r; ws.close(); });
})();
