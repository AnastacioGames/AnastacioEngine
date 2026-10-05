// Opens net_web_watch.html in headless Chromium and waits for "NETWEB PASS|FAIL" in the page title.
//   node net_web_browser.js <http url of net_web_watch.html with ?host=&port=&hash=>
const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({ executablePath: process.env.CHROMIUM || undefined });
  const page = await browser.newPage();
  page.on('console', (msg) => console.log('[page] ' + msg.text()));
  await page.goto(process.argv[2]);
  let title = '';
  try {
    await page.waitForFunction(() => document.title.startsWith('NETWEB'), null, { timeout: 30000 });
    title = await page.title();
  } catch (e) {
    title = 'NETWEB FAIL timeout (' + (await page.title()) + ')';
  }
  console.log(title + ' (' + (await browser.version()) + ')');
  await browser.close();
  process.exit(title.startsWith('NETWEB PASS') ? 0 : 1);
})();
