// Prova de capacidades do runtime Web no Chrome (sem julgamento visual): dispara entrada real por CDP
// e confere as linhas que o jogo de teste (web-smoke) imprime. Serve de evidencia para o manifesto
// do runtime (tools/web/make-runtime-manifest.py --evidence).
//
// Uso: node tools/web/verify-capabilities.cjs <url> <modo> [porta-cdp=9333]
//   modo touch    : toque (touchStart/End) no canvas deve virar clique de mouse ("mouse click flipped")
//   modo sim      : jogo web-capabilities: fisica, addObject/endObject, addScene (overlay) e replace de cena
//   modo audio    : jogo web-audio: tom WAV em loop; confere mixer ativo e amplitude nao nula na saida Web Audio
//   modo render   : jogo web-render: sobe e roda 8 s sem excecao (o visual e julgado pelo usuario)
//   modo filters  : 1..0,Q (filtros simples ligam/desligam) e W,E,R,T (embutidos) sem erro de shader
// Requer Chrome ja aberto com --remote-debugging-port=<porta-cdp>. Sai com 0 se todas as expectativas baterem.
const [url, mode, port = '9333'] = process.argv.slice(2);
if (!url || !mode) { console.error('uso: verify-capabilities.cjs <url> <touch|filters|sim|audio> [porta-cdp]'); process.exit(2); }

(async () => {
  const target = await (await fetch(`http://127.0.0.1:${port}/json/new?about:blank`, { method: 'PUT' })).json();
  const ws = new WebSocket(target.webSocketDebuggerUrl);
  await new Promise(r => (ws.onopen = r));
  let id = 0; const pending = new Map(); const logs = [];
  ws.onmessage = e => {
    const m = JSON.parse(e.data);
    if (m.id) { pending.get(m.id)?.(m.result); pending.delete(m.id); }
    else if (m.method === 'Runtime.consoleAPICalled') logs.push(m.params.args.map(a => a.value ?? a.description).join(' '));
    else if (m.method === 'Runtime.exceptionThrown') logs.push('[exception] ' + JSON.stringify(m.params.exceptionDetails.text) + ' ' + ((m.params.exceptionDetails.exception || {}).description || '').slice(0, 1500));
  };
  const call = (method, params = {}) => new Promise(r => { pending.set(++id, r); ws.send(JSON.stringify({ id, method, params })); });
  const evalJs = async expr => (await call('Runtime.evaluate', { expression: expr, returnByValue: true })).result?.value;
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const key = async (k, code, vk) => {
    for (const type of ['keyDown', 'keyUp']) {
      await call('Input.dispatchKeyEvent', { type, key: k, code, windowsVirtualKeyCode: vk, nativeVirtualKeyCode: vk });
      await sleep(250);
    }
  };

  if (mode === 'audio') {
    // Espia a saida Web Audio (SDL usa ScriptProcessor): conta frames e a amplitude maxima do que o jogo mixou.
    await call('Page.addScriptToEvaluateOnNewDocument', { source: `(function(){
      var A = window.__aud = { ctx: 0, procs: 0, frames: 0, peak: 0 };
      var AC = window.AudioContext || window.webkitAudioContext; if (!AC) return;
      var desc = Object.getOwnPropertyDescriptor(ScriptProcessorNode.prototype, 'onaudioprocess');
      var W = function () { var c = new (Function.prototype.bind.apply(AC, [null].concat([].slice.call(arguments))))(); A.ctx++; A.last = c;
        var orig = c.createScriptProcessor.bind(c);
        c.createScriptProcessor = function () { var n = orig.apply(null, arguments); A.procs++;
          Object.defineProperty(n, 'onaudioprocess', { configurable: true, get: function () { return desc.get.call(n); },
            set: function (f) { desc.set.call(n, function (e) { f.call(this, e); var b = e.outputBuffer; A.frames += b.length;
              for (var ch = 0; ch < b.numberOfChannels; ch++) { var d = b.getChannelData(ch); for (var i = 0; i < d.length; i++) { var v = Math.abs(d[i]); if (v > A.peak) A.peak = v; } } }); } });
          return n; };
        return c; };
      W.prototype = AC.prototype; window.AudioContext = W; window.webkitAudioContext = W; })();` });
  }
  await call('Runtime.enable'); await call('Page.enable');
  await call('Network.enable'); await call('Network.setCacheDisabled', { cacheDisabled: true });
  await call('Emulation.setTouchEmulationEnabled', { enabled: true, maxTouchPoints: 5 });
  await call('Page.navigate', { url: url + (url.includes('?') ? '&' : '?') + 'debug=1' });
  let state = 'loading';
  for (let i = 0; i < 60 && state === 'loading'; i++) {
    await sleep(500);
    state = await evalJs(`(function(){var b=document.getElementById('play'),e=document.getElementById('error');
      if(e&&!e.hidden)return 'error';return b&&!b.disabled?'ready':'loading';})()`);
  }
  const checks = [];
  const expect = (name, ok) => checks.push([name, !!ok]);
  expect('pacote carregou', state === 'ready');
  if (state === 'ready') {
    await call('Runtime.evaluate', { expression: `document.getElementById('play').click()`, userGesture: true });
    await sleep(3000);
    const box = JSON.parse(await evalJs(`JSON.stringify(document.getElementById('canvas').getBoundingClientRect())`));
    const x = box.x + box.width / 2, y = box.y + box.height / 2;
    if (mode === 'touch') {
      const before = logs.filter(l => /mouse click flipped/.test(l)).length;
      for (let n = 0; n < 3; n++) {
        await call('Input.dispatchTouchEvent', { type: 'touchStart', touchPoints: [{ x, y, id: 1 }] });
        await sleep(150);
        await call('Input.dispatchTouchEvent', { type: 'touchEnd', touchPoints: [] });
        await sleep(500);
      }
      await sleep(1000);
      const got = logs.filter(l => /mouse click flipped/.test(l)).length - before;
      expect('toque virou clique (3 toques)', got >= 1);
      console.log('cliques observados:', got);
    } else if (mode === 'sim') {
      await sleep(25000);
      const has = re => logs.some(l => re.test(l));
      expect('cena A rodando', has(/\[cap\] scene A running/));
      expect('fisica: corpo rigido cai', has(/\[cap\] physics fell/));
      expect('addObject cria', has(/\[cap\] spawn ok/));
      expect('objeto criado presente na cena', has(/\[cap\] spawn present=1/));
      expect('endObject remove', has(/\[cap\] endObject ok/));
      expect('addScene (overlay) cria a cena B', has(/\[cap\] overlay ok/) && has(/\[cap\] scene B running/));
      expect('replace troca para a cena C', has(/\[cap\] scene C running/));
      expect('cena C segue viva', has(/\[cap\] scene C alive after 60 ticks/));
      logs.filter(l => /\[cap\]/.test(l)).forEach(l => console.log('  ' + l));
    } else if (mode === 'audio') {
      await sleep(9000);
      const has = re => logs.some(l => re.test(l));
      const a = JSON.parse(await evalJs(`JSON.stringify({ctx:__aud.ctx,procs:__aud.procs,frames:__aud.frames,peak:__aud.peak,state:__aud.last&&__aud.last.state,rate:__aud.last&&__aud.last.sampleRate})`));
      console.log('web audio:', JSON.stringify(a));
      expect('cena de audio rodando', has(/\[aud\] scene running/));
      expect('actuator de som ativado', has(/\[aud\] sound actuator activated/));
      expect('jogo segue vivo', has(/\[aud\] still alive/));
      expect('AudioContext criado pelo runtime', a.ctx >= 1 && a.procs >= 1);
      expect('AudioContext em execucao', a.state === 'running');
      expect('mixer avancou (frames)', a.frames > 0);
      expect('saida com amplitude (tom audivel)', a.peak > 0.05);
      logs.filter(l => /\[aud\]|audio|Audaspace|aud:/i.test(l)).slice(0, 15).forEach(l => console.log('  ' + l.slice(0, 200)));
    } else if (mode === 'render') {
      await sleep(8000);
      const has = re => logs.some(l => re.test(l));
      expect('cena de render rodando', has(/\[render\] scene running/));
      expect('sem excecao/aborto no loop', !has(/\[exception\]|Aborted|\[ABORT\]/));
    } else if (mode === 'filters') {
      const KEYS = [['1', 'Digit1', 49, 'BLUR'], ['2', 'Digit2', 50, 'SHARPEN'], ['3', 'Digit3', 51, 'DILATION'],
        ['4', 'Digit4', 52, 'EROSION'], ['5', 'Digit5', 53, 'LAPLACIAN'], ['6', 'Digit6', 54, 'SOBEL'],
        ['7', 'Digit7', 55, 'PREWITT'], ['8', 'Digit8', 56, 'GRAYSCALE'], ['9', 'Digit9', 57, 'SEPIA'],
        ['0', 'Digit0', 48, 'INVERT'], ['q', 'KeyQ', 81, 'OUTLINE'],
        ['w', 'KeyW', 87, 'SSAO'], ['e', 'KeyE', 69, 'BLOOM'], ['r', 'KeyR', 82, 'LIGHTSCATTER'], ['t', 'KeyT', 84, 'SSR']];
      for (const [k, code, vk, name] of KEYS) {
        const before = logs.length;
        await key(k, code, vk);
        await sleep(1200);
        const seen = logs.slice(before).some(l => new RegExp('filter ON.*' + name).test(l));
        expect('filtro ' + name + ' ligou', seen);
        if (!['w', 'e', 'r', 't'].includes(k)) {
          await key(k, code, vk); await sleep(800);
          expect('filtro ' + name + ' desligou', logs.some(l => new RegExp('filter OFF.*' + name).test(l)));
        }
      }
      const log = await evalJs(`document.getElementById('log').textContent`) || '';
      const m = /.*(shader.*(fail|error)|ERROR: [0-9]+:[0-9]+|Aborted|\[ABORT\]).*/i.exec(log + String.fromCharCode(10) + logs.join(String.fromCharCode(10)));
      if (m) console.log('linha suspeita:', m[0].slice(0, 300));
      expect('sem erro de shader/aborto', !m);
    }
  }
  for (const [n, ok] of checks) console.log((ok ? 'OK   ' : 'FALHA') + ' ' + n);
  const ok = checks.every(c => c[1]);
  if (!ok) console.log('--- logs (ultimos 25) ---\n' + logs.slice(-25).join('\n'));
  await fetch(`http://127.0.0.1:${port}/json/close/${target.id}`);
  process.exitCode = ok ? 0 : 1;
  await new Promise(r => { ws.onclose = r; ws.close(); });
})();
