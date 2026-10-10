// Log-only smoke test; does not capture screenshots or assert appearance.
// node tools/test_material_atlas_web.cjs <URL> <playwright-core path> <browser exe>
const { chromium } = require(process.argv[3]);
(async () => {
  const browser = await chromium.launch({executablePath: process.argv[4], headless: true});
  try {
    const page = await browser.newPage();
    let passed = false;
    const errors = [];
    page.on('console', message => {
      console.log(message.text());
      if (message.text().includes('ANASTACIO_ATLAS_RUNTIME_PASS')) passed = true;
    });
    page.on('pageerror', error => { errors.push(error.message); console.error(error.message); });
    await page.goto(process.argv[2]);
    await page.waitForFunction(() => !document.getElementById('play').disabled, null, {timeout: 60000});
    await page.locator('#play').click();
    const deadline = Date.now() + 45000;
    while (!passed && !errors.length && Date.now() < deadline) await page.waitForTimeout(250);
    if (!passed || errors.length) throw new Error('Atlas runtime marker missing or browser exception: ' + errors);
    console.log('ANASTACIO_ATLAS_WEB_PASS ' + browser.version());
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
