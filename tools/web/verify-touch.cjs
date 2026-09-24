// Verificacao automatizada do overlay de controle na tela (toque -> Module.rangePad -> gamepad 0 do runtime), com dois
// dedos ao mesmo tempo via CDP Input.dispatchTouchEvent. Usa a cena de tools/tests/web_profile/make_pad_project.py.
//
// Uso: node tools/web/verify-touch.cjs http://127.0.0.1:8792/ [porta-cdp=9333]
// Requer Chrome/Edge aberto com --remote-debugging-port=<porta-cdp> (ver docs/web-deploy.md). Abre com ?touch=1
// (o navegador do PC nao e pointer: coarse): primeiro o layout padrao do pacote (stick + A/B, alvo gamepad),
// depois ?touchlayout=wasd (alvo tecla, junto com o teclado fisico emulado pelo CDP).
const url = process.argv[2];
const port = process.argv[3] || '9333';
if (!url) { console.error('uso: verify-touch.cjs <url> [porta-cdp]'); process.exit(2); }

(async () => {
  let target = null, ws = null;
  let id = 0; const pending = new Map(); const errors = [];
  const closeTab = async () => {
    if (!target) return;
    await fetch(`http://127.0.0.1:${port}/json/close/${target.id}`);
    await new Promise(r => { ws.onclose = r; ws.close(); });
  };
  const call = (method, params = {}) => new Promise(r => { pending.set(++id, r); ws.send(JSON.stringify({ id, method, params })); });
  const evalJs = async expr => (await call('Runtime.evaluate', { expression: expr, returnByValue: true })).result?.value;
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const logText = async () => (await evalJs(`document.getElementById('log').textContent`)) || '';
  const lastPad = async from => {
    const lines = (await logText()).slice(from).split('\n').filter(l => /\[pad\] connected=/.test(l));
    return lines.length ? lines[lines.length - 1] : '';
  };
  const padState = () => evalJs(`JSON.stringify(Module.rangePad)`).then(JSON.parse);
  const center = sel => evalJs(`(function(){var r=document.querySelector(${JSON.stringify(sel)}).getBoundingClientRect();
    return [r.left + r.width / 2, r.top + r.height / 2, r.width / 2];})()`);
  const touch = (type, points) => call('Input.dispatchTouchEvent', {
    type, touchPoints: points.map(([x, y, pid]) => ({ x, y, id: pid, radiusX: 4, radiusY: 4, force: 1 })) });
  const results = [];
  const check = (name, ok, detail) => { results.push(ok); console.log(`${ok ? 'OK  ' : 'FALHA'} ${name}: ${detail}`); };

  // Cada layout numa aba nova: recarregar na mesma aba deixava o toque do CDP sem chegar a pagina (Edge headless).
  const open = async query => {
    await closeTab();
    target = await (await fetch(`http://127.0.0.1:${port}/json/new?about:blank`, { method: 'PUT' })).json();
    ws = new WebSocket(target.webSocketDebuggerUrl);
    await new Promise(r => (ws.onopen = r));
    ws.onmessage = e => {
      const m = JSON.parse(e.data);
      if (m.id) { pending.get(m.id)?.(m.error ? { error: m.error } : m.result); pending.delete(m.id); }
      else if (m.method === 'Runtime.exceptionThrown') errors.push(JSON.stringify(m.params.exceptionDetails.text));
    };
    await call('Runtime.enable'); await call('Page.enable');
    await call('Network.enable'); await call('Network.setCacheDisabled', { cacheDisabled: true });
    await call('Emulation.setDeviceMetricsOverride', { width: 960, height: 540, deviceScaleFactor: 1, mobile: false });
    await call('Emulation.setTouchEmulationEnabled', { enabled: true, maxTouchPoints: 5 });
    await call('Page.navigate', { url: url + (url.includes('?') ? '&' : '?') + 'debug=1&touch=1' + query });
    let state = 'loading';
    for (let i = 0; i < 60 && state === 'loading'; i++) {
      await sleep(500);
      state = await evalJs(`(function(){var b=document.getElementById('play'),e=document.getElementById('error');
        if(e&&!e.hidden)return 'error';return b&&!b.disabled?'ready':'loading';})()`);
    }
    if (state !== 'ready')
      console.log('pagina nao ficou pronta:', state, await evalJs(`document.getElementById('error').textContent`));
    else await evalJs(`document.getElementById('play').click()`);
    await sleep(2500);
    return state === 'ready';
  };
  if (!await open('')) { process.exitCode = 1; return; }

  // 1. Overlay visivel com o layout padrao e pad ativo.
  const shown = await evalJs(`(function(){var t=document.getElementById('touch');
    return !t.hidden && !!t.querySelector('.zone.left .base') && t.querySelectorAll('.btn').length;})()`);
  check('overlay com stick + 2 botoes', shown === 2, `botoes=${shown}`);
  let line = await lastPad(0);
  // Com controle fisico ligado o nome e o dele ("Standard Gamepad"): o pad virtual junta no mesmo indice 0.
  check('pad ativo vira joysticks[0]', /connected=True/.test(line), line || '(nenhuma linha [pad])');
  const maps = ((await logText()).match(/\[pad\] maps [^\n]*/) || ['(sem linha maps)'])[0];
  check('KeyMapping/Pad.json carregado pelo Input System', /\[pad\] maps \['Pad'\]/.test(maps), maps);

  // 2. Dois dedos: stick arrastado ate a borda direita e botao A apertado ao mesmo tempo.
  const [bx, by, br] = await center('#touch .zone.left .base');
  const [ax, ay] = await center('#touch .btn');
  let mark = (await logText()).length;
  await touch('touchStart', [[bx, by, 1]]);
  await touch('touchMove', [[bx + br * 0.5, by, 1]]);
  await touch('touchMove', [[bx + br * 1.5, by, 1]]);
  await touch('touchStart', [[bx + br * 1.5, by, 1], [ax, ay, 2]]);
  await sleep(300);
  let p = await padState();
  check('stick a direita (LX 1, LY 0)', Math.abs(p.axes[0] - 1) < 1e-6 && Math.abs(p.axes[1]) < 1e-6, JSON.stringify(p.axes));
  check('botao A junto com o stick', p.buttons === 1, `buttons=${p.buttons}`);
  await sleep(1500);
  line = await lastPad(mark);
  const log2 = (await logText()).slice(mark);
  check('engine ve stick e A juntos', /axes=\[1\.0, 0\.0,/.test(line) && /buttons=\[0\]/.test(line), line || '-');
  check('sensor Joystick A down', /\[pad\] sensor A down/.test(log2), '-');
  check('Input System: acao Pular pelo botao A (binding JOYSTICK)', /\[pad\] map Pular down/.test(log2), '-');

  // 3. Soltar so o botao: o stick continua; depois soltar o stick: tudo volta a zero.
  await touch('touchEnd', [[ax, ay, 2]]);  // no CDP o touchEnd lista os pontos que sobem
  await sleep(200);
  p = await padState();
  check('soltar A mantem o stick', p.buttons === 0 && Math.abs(p.axes[0] - 1) < 1e-6, JSON.stringify(p));
  await touch('touchEnd', []);
  await sleep(200);
  p = await padState();
  check('soltar tudo zera o pad', p.buttons === 0 && p.axes.every(v => v === 0), JSON.stringify(p));

  // 4. Dedo segurando o stick na diagonal e a janela perde o foco: nada fica preso.
  await touch('touchStart', [[bx, by, 3]]);
  await touch('touchMove', [[bx - br * 0.4, by - br * 0.3, 3]]);
  await sleep(200);
  p = await padState();
  const diag = p.axes[0] < -0.3 && p.axes[1] < -0.2;
  await evalJs(`window.dispatchEvent(new Event('blur'))`);
  await sleep(200);
  const after = await padState();
  check('diagonal e soltura ao perder o foco', diag && after.axes.every(v => v === 0),
        `${JSON.stringify(p.axes.slice(0, 2))} -> ${JSON.stringify(after.axes.slice(0, 2))}`);
  await touch('touchEnd', []);

  // 5. Toque fora dos controles nao mexe no pad (vai para o canvas).
  await touch('touchStart', [[480, 80, 4]]);
  await sleep(200);
  p = await padState();
  await touch('touchEnd', []);
  check('toque fora dos controles nao aciona o pad', p.buttons === 0 && p.axes.every(v => v === 0), JSON.stringify(p));

  // 5b. Checklist do celular (plano A1): dois botoes juntos, arrastar para fora, toque cancelado e pagina escondida.
  const [bbx, bby] = await evalJs(`(function(){var r=document.querySelectorAll('#touch .btn')[1].getBoundingClientRect();
    return [r.left + r.width / 2, r.top + r.height / 2];})()`);
  mark = (await logText()).length;
  await touch('touchStart', [[ax, ay, 5]]);
  await touch('touchStart', [[ax, ay, 5], [bbx, bby, 6]]);
  await sleep(300);
  p = await padState();
  check('dois botoes juntos (A e B)', p.buttons === 3, `buttons=${p.buttons}`);
  await sleep(1200);
  line = await lastPad(mark);
  check('engine ve A e B juntos', /buttons=\[0, 1\]/.test(line), line || '-');
  await touch('touchEnd', []);
  await sleep(200);
  // Dedo do stick arrastado ate em cima do botao A: continua sendo o stick (pointer capture) e nao aperta A.
  await touch('touchStart', [[bx, by, 7]]);
  await touch('touchMove', [[bx + br, by, 7]]);
  await touch('touchMove', [[ax, ay, 7]]);
  await sleep(200);
  p = await padState();
  check('arrastar para fora do stick: segue no stick e nao aperta A',
        p.buttons === 0 && Math.hypot(p.axes[0], p.axes[1]) > 0.99, JSON.stringify(p));
  await touch('touchEnd', []);
  await sleep(200);
  p = await padState();
  check('soltar fora do controle zera o stick', p.axes.every(v => v === 0), JSON.stringify(p));
  // Toque cancelado pelo sistema (gesto do Android, notificacao por cima).
  await touch('touchStart', [[bx, by, 8]]);
  await touch('touchMove', [[bx, by - br, 8]]);
  await touch('touchStart', [[bx, by - br, 8], [ax, ay, 9]]);
  await sleep(200);
  const held = await padState();
  await touch('touchCancel', []);
  await sleep(200);
  p = await padState();
  check('touchcancel solta stick e botao', held.buttons === 1 && held.axes[1] < -0.9 &&
        p.buttons === 0 && p.axes.every(v => v === 0), `${JSON.stringify(held)} -> ${JSON.stringify(p)}`);
  // Troca de app: a pagina fica escondida com o dedo ainda no controle.
  await touch('touchStart', [[bx, by, 10]]);
  await touch('touchMove', [[bx + br, by, 10]]);
  await sleep(200);
  const moving = await padState();
  await evalJs(`Object.defineProperty(document, 'hidden', { configurable: true, get: () => true });
    document.dispatchEvent(new Event('visibilitychange')); delete document.hidden;`);
  await sleep(200);
  p = await padState();
  check('pagina escondida (troca de app) solta o stick', moving.axes[0] > 0.9 && p.axes.every(v => v === 0),
        `${JSON.stringify(moving.axes.slice(0, 2))} -> ${JSON.stringify(p.axes.slice(0, 2))}`);
  await touch('touchEnd', []);

  // 6. Alvo tecla (layout wasd): o stick vira W/A/S/D e o botao, espaco, pelo teclado do jogo.
  if (!await open('&touchlayout=wasd')) { process.exitCode = 1; return; }
  let log6 = await logText();
  // Codigos da tabela da pagina (W=45, SPACE=8, UPARROW=72) iguais aos do bge.events.
  check('codigos de tecla iguais aos do bge.events', /\[pad\] codes W=45 SPACE=8 UPARROW=72/.test(log6),
        (log6.match(/\[pad\] codes[^\n]*/) || ['(sem linha codes)'])[0]);
  const [kx, ky, kr] = await center('#touch .zone.left .base');
  const [sx, sy] = await center('#touch .btn');
  mark = (await logText()).length;
  await touch('touchStart', [[kx, ky, 11]]);
  await touch('touchMove', [[kx, ky - kr * 1.2, 11]]);
  await touch('touchStart', [[kx, ky - kr * 1.2, 11], [sx, sy, 12]]);
  await sleep(300);
  p = await padState();
  check('stick para cima + botao = W e espaco', JSON.stringify(p.keys) === '[45,8]' && p.axes.every(v => v === 0) &&
        p.buttons === 0, JSON.stringify(p));
  await sleep(500);
  log6 = (await logText()).slice(mark);
  check('jogo ve W e espaco apertados', /\[pad\] key W down/.test(log6) && /\[pad\] key SPACE down/.test(log6), '-');
  check('Input System: acao Pular pelo espaco (binding KEYBOARD)', /\[pad\] map Pular down/.test(log6), '-');
  await touch('touchEnd', []);
  await sleep(500);
  log6 = (await logText()).slice(mark);
  check('soltar o toque solta W e espaco', /\[pad\] key W up/.test(log6) && /\[pad\] key SPACE up/.test(log6), '-');

  // 7. Origem separada: W segurado no teclado fisico nao solta quando o toque solta.
  const key = (type, code, vk) => call('Input.dispatchKeyEvent',
    { type, key: code.slice(-1).toLowerCase(), code, windowsVirtualKeyCode: vk, nativeVirtualKeyCode: vk });
  await evalJs(`document.getElementById('canvas').focus()`);
  mark = (await logText()).length;
  await key('keyDown', 'KeyW', 87);
  await sleep(300);
  await touch('touchStart', [[kx, ky, 13]]);
  await touch('touchMove', [[kx, ky - kr * 1.2, 13]]);
  await sleep(300);
  const during = await padState();
  await touch('touchEnd', []);
  await sleep(500);
  let log7 = (await logText()).slice(mark);
  const downs = (log7.match(/\[pad\] key W down/g) || []).length;
  check('teclado segura W: toque sobe e W continua',
        JSON.stringify(during.keys) === '[45]' && downs === 1 && !/\[pad\] key W up/.test(log7),
        `toque keys=${JSON.stringify(during.keys)}, W down=${downs}, W up=${/key W up/.test(log7)}`);
  await key('keyUp', 'KeyW', 87);
  await sleep(500);
  log7 = (await logText()).slice(mark);
  check('W solta quando o teclado solta', /\[pad\] key W up/.test(log7), '-');

  if (errors.length) console.log('--- excecoes JS ---\n' + errors.join('\n'));
  process.exitCode = results.every(Boolean) && !errors.length ? 0 : 1;
  console.log(process.exitCode === 0 ? 'TOUCH: PASS' : 'TOUCH: FAIL');
  // Sem process.exit(): no Node 24 no Windows ele dispara um assert do libuv com o WebSocket aberto.
  await closeTab();
})();
