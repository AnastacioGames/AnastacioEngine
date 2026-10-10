// Logs/state/audio only. Auditory confirmation is left to the listener.
const { chromium } = require('../../debug-logs/atlas-browser/node_modules/playwright-core');
(async () => {
  const browser = await chromium.launch({executablePath: 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe', headless: true});
  try {
    const page = await browser.newPage();
    const logs = [], errors = [];
    page.on('console', msg => { logs.push(msg.text()); if (msg.text().includes('[reverb-ab]')) console.log(msg.text()); });
    page.on('pageerror', err => errors.push(err.message));
    await page.goto(process.argv[2]);
    await page.waitForFunction(() => !document.getElementById('play').disabled, null, {timeout: 60000});
    await page.locator('#play').click();
    await page.waitForTimeout(10500);
    const switches = logs.filter(s => s.includes('[reverb-ab] SWITCH')).map(s => {
      const m = s.match(/phase=(\d+) state=(\w+) seconds=(-?[\d.]+)/);
      return {phase: +m[1], state: m[2], seconds: +m[3]};
    });
    const audio = await page.evaluate(() => {
      const a = Module.rangeAudio;
      return a && {backend: a.backend, frames: a.frames, peak: a.peak, state: a.ctx.state};
    });
    console.log('AUDIO', JSON.stringify(audio));
    if (errors.length || logs.some(s => s.includes('[reverb-ab] STATE') && s.endsWith('FAIL'))) throw Error('Runtime errors: ' + errors);
    if (switches.length < 5) throw Error('Missing alternations');
    for (let i = 1; i < switches.length; ++i) {
      if (switches[i].state === switches[i-1].state || Math.abs(switches[i].seconds - switches[i-1].seconds - 2) > 0.2) throw Error('Invalid alternation timing');
    }
    if (!audio || audio.frames <= 0 || audio.peak <= 0.001 || audio.state !== 'running') throw Error('No active audio output');
    console.log('REVERB_AB_WEB_RUNTIME_PASS (EFX audibility not asserted)');
  } finally { await browser.close(); }
})().catch(err => { console.error(err); process.exitCode = 1; });
