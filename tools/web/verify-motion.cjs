// Verificacao automatizada de bge.logic.motion no runtime Web, com sensores emulados pelo CDP
// (Emulation.setSensorOverrideReadings). Usa a cena gerada por
// tools/tests/web_profile/make_motion_project.py, que imprime "[motion] ..." a cada 60 quadros.
//
// Uso: node tools/web/verify-motion.cjs http://127.0.0.1:8791/ [porta-cdp=9333]
// Requer Chrome/Edge aberto com --remote-debugging-port=<porta-cdp> (ver docs/web-deploy.md).
// Nao substitui o teste no celular: prova a cadeia evento -> JS -> wasm -> Python e as conversoes.
const url = process.argv[2];
const port = process.argv[3] || '9333';
if (!url) { console.error('uso: verify-motion.cjs <url> [porta-cdp]'); process.exit(2); }

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
  // Ultima linha "[motion] available=..." impressa pelo Python depois de `from` caracteres de log.
  const lastMotion = async from => {
    const lines = (await logText()).slice(from).split('\n').filter(l => /\[motion\] available=/.test(l));
    return lines.length ? lines[lines.length - 1] : '';
  };
  const results = [];
  const check = (name, ok, detail) => { results.push(ok); console.log(`${ok ? 'OK  ' : 'FALHA'} ${name}: ${detail}`); };

  await call('Runtime.enable'); await call('Page.enable');
  await call('Network.enable'); await call('Network.setCacheDisabled', { cacheDisabled: true });
  // A emulacao precisa existir antes da pagina registrar os listeners: sem sensor na carga, o Chrome
  // entrega um evento nulo e nao volta a procurar (no celular o sensor ja existe).
  const setReadings = async (accel, gyro) => {
    await call('Emulation.setSensorOverrideReadings', { type: 'accelerometer', reading: { xyz: accel } });
    await call('Emulation.setSensorOverrideReadings', { type: 'linear-acceleration', reading: { xyz: { x: 0, y: 0, z: 0 } } });
    await call('Emulation.setSensorOverrideReadings', { type: 'gyroscope', reading: { xyz: gyro } });
  };
  for (const type of ['accelerometer', 'linear-acceleration', 'gyroscope']) {
    const r = await call('Emulation.setSensorOverrideEnabled', { enabled: true, type });
    if (r.error) { check('emulacao de sensor', false, `${type}: ${r.error.message}`); process.exitCode = 1; return; }
  }
  await setReadings({ x: 0, y: 0, z: 9.8 }, { x: 0, y: 0, z: 0 });
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

  // 1. Celular deitado de face para cima: sensor ativo, sem inclinacao.
  await sleep(4000);
  let line = await lastMotion(0);
  check('deitado: available e tilt zero', /available=True tilt=\((-)?0\.00, (-)?0\.00\)/.test(line), line || '(nenhuma linha [motion])');

  // 2. Celular em retrato, borda direita 30 graus abaixo, girando (0.3, 0.6, 1) rad/s em x, y, z.
  //    Gravidade no sentido W3C (para cima): x = -9.8*sin30, z = 9.8*cos30.
  await setReadings({ x: -4.9, y: 0, z: 8.487 }, { x: 0.3, y: 0.6, z: 1 });
  let mark = (await logText()).length;
  await sleep(4000);
  line = await lastMotion(mark);
  const m = /tilt=\(([-\d.]+), ([-\d.]+)\).*gyro=\(([-\d.]+), ([-\d.]+), ([-\d.]+)\)/.exec(line);
  check('available com sensor', /available=True/.test(line), line || '(nenhuma linha [motion])');
  check('tilt x ~ +0.5 (bola rola para a direita)', !!m && Math.abs(+m[1] - 0.5) < 0.05 && Math.abs(+m[2]) < 0.05,
        m ? `tilt=(${m[1]}, ${m[2]})` : '-');
  check('gyro ~ (0.3, 0.6, 1) rad/s', !!m && Math.abs(+m[3] - 0.3) < 0.05 && Math.abs(+m[4] - 0.6) < 0.05 && Math.abs(+m[5] - 1) < 0.05,
        m ? `gyro=(${m[3]}, ${m[4]}, ${m[5]})` : '-');

  // 2b. Mesma pose do aparelho com a tela em paisagem (girada 90 graus anti-horario): a borda direita do
  //     aparelho vira o topo da tela, entao a bola rola para cima (tilt y ~ +0.5); o giro do aparelho
  //     (0.3, 0.6, 1) vira (-0.6, 0.3, 1) nos eixos da tela.
  const size = await evalJs(`({w: innerWidth, h: innerHeight})`);
  await call('Emulation.setDeviceMetricsOverride', { width: size.w, height: size.h, deviceScaleFactor: 1, mobile: false,
    screenOrientation: { type: 'landscapePrimary', angle: 90 } });
  mark = (await logText()).length;
  await sleep(4000);
  line = await lastMotion(mark);
  const l = /tilt=\(([-\d.]+), ([-\d.]+)\).*gyro=\(([-\d.]+), ([-\d.]+), ([-\d.]+)\)/.exec(line);
  check('paisagem: tilt y ~ +0.5, gyro ~ (-0.6, 0.3, 1)', !!l && Math.abs(+l[1]) < 0.05 && Math.abs(+l[2] - 0.5) < 0.05 &&
        Math.abs(+l[3] + 0.6) < 0.05 && Math.abs(+l[4] - 0.3) < 0.05 && Math.abs(+l[5] - 1) < 0.05, line || '-');
  await call('Emulation.clearDeviceMetricsOverride');
  await sleep(500);

  // 3. Toque na tela: calibrate() toma a posicao atual como neutra, tilt volta a zero.
  mark = (await logText()).length;
  const box = await evalJs(`(function(){var r=document.getElementById('canvas').getBoundingClientRect();
    return {x:r.left+r.width/2,y:r.top+r.height/2};})()`);
  for (const type of ['mousePressed', 'mouseReleased']) {
    await call('Input.dispatchMouseEvent', { type, x: box.x, y: box.y, button: 'left', clickCount: 1 });
    await sleep(150);
  }
  await sleep(4000);
  const log3 = (await logText()).slice(mark);
  line = await lastMotion(mark);
  check('calibrate() pelo toque', /\[motion\] calibrate: True/.test(log3), (log3.match(/\[motion\] calibrate: \w+/) || ['(nao chamado)'])[0]);
  check('tilt zero depois de calibrar', /tilt=\((-)?0\.00, (-)?0\.00\)/.test(line), line || '-');

  if (errors.length) console.log('--- excecoes JS ---\n' + errors.join('\n'));
  await fetch(`http://127.0.0.1:${port}/json/close/${target.id}`);
  process.exitCode = results.every(Boolean) && !errors.length ? 0 : 1;
  console.log(process.exitCode === 0 ? 'MOTION: PASS' : 'MOTION: FAIL');
  // Sem process.exit(): no Node 24 no Windows ele dispara um assert do libuv com o WebSocket aberto.
  await new Promise(r => { ws.onclose = r; ws.close(); });
})();
