const { chromium } = require('/root/clawd/novaire-operations-system/node_modules/playwright');

(async () => {
  const browser = await chromium.launch({headless:true, executablePath:'/snap/bin/chromium', args:['--no-sandbox']});
  const page = await browser.newPage({viewport:{width:1280,height:900}});
  const errors = [];
  page.on('pageerror', error => errors.push(String(error)));
  const target = process.env.NOVAIRE_ACCORDION_URL || 'http://127.0.0.1:8765/index.html';
  await page.goto(target, {waitUntil:'domcontentloaded'});

  const edition = await page.locator('#quotes-card').getAttribute('data-edition');
  await page.evaluate(value => localStorage.setItem('nv_meditation_card_viewed', value), edition);
  await page.reload({waitUntil:'domcontentloaded'});

  const accordions = page.locator('details.signal-accordion');
  const count = await accordions.count();
  const failures = [];
  for (let index = 0; index < count; index += 1) {
    const details = accordions.nth(index);
    const id = await details.getAttribute('id') || `accordion-${index}`;
    await details.evaluate(node => node.open = false);
    await details.locator(':scope > summary').evaluate(node => node.click());
    await page.waitForTimeout(40);
    if (!(await details.evaluate(node => node.open))) failures.push(`${id}: would not open`);
    await details.locator(':scope > summary').evaluate(node => node.click());
    await page.waitForTimeout(40);
    if (await details.evaluate(node => node.open)) failures.push(`${id}: would not close`);
  }

  if (errors.length || failures.length) throw new Error([...errors, ...failures].join('\n'));
  console.log(`accordion interactions: ok (${count} dropdowns)`);
  await browser.close();
})().catch(error => { console.error(error.stack || error); process.exit(1); });
