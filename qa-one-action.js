const { chromium } = require('/root/clawd/novaire-operations-system/node_modules/playwright');

(async () => {
  const browser = await chromium.launch({ headless: true, executablePath: '/snap/bin/chromium', args: ['--no-sandbox'] });
  const page = await browser.newPage({ viewport: { width: 390, height: 844 } });
  await page.goto('http://127.0.0.1:8765/?qa=keystone', { waitUntil: 'load' });
  await page.evaluate(() => localStorage.clear());
  await page.reload();

  await page.locator('#keystone-input').fill('Build the retreat deposit page and deploy it');
  await page.locator('#keystone-done').click();
  if (await page.locator('#action-steps-grid .action-step').count() !== 1) throw Error('not exactly one daily action');
  const first = await page.locator('.action-step-ask').innerText();
  if (!first.includes('Build the retreat deposit page and deploy it')) throw Error('action is not tied to exact Keystone');
  if (!(await page.locator('.action-step-title').innerText()).includes('buyer closer')) throw Error('retreat intent was not classified');

  await page.getByRole('button', { name: 'Ricies' }).click();
  const retry = await page.locator('.action-step-ask').innerText();
  if (!retry.includes('Build the retreat deposit page and deploy it')) throw Error('replacement lost the Keystone');

  await page.locator('#keystone-input').fill('Review the uranium portfolio thesis');
  await page.locator('#keystone-input').press('Enter');
  const reset = await page.locator('.action-step-ask').innerText();
  if (!reset.includes('Review the uranium portfolio thesis')) throw Error('Enter did not set the new Keystone');
  if (!(await page.locator('.action-step-title').innerText()).includes('thesis into a rule')) throw Error('new Keystone did not reset to tailored first action');

  await page.locator('#keystone-input').fill('Clean up Novairecito OS to show Mizel');
  await page.locator('#keystone-input').press('Enter');
  const osAction = await page.locator('.action-step-ask').innerText();
  if (!osAction.includes('Clean up Novairecito OS to show Mizel')) throw Error('OS action lost the exact Keystone');
  if (!(await page.locator('.action-step-title').innerText()).includes('verified improvement')) throw Error('OS cleanup was misclassified');
  if (/laundry|vacuum/i.test(osAction)) throw Error('OS cleanup leaked into the housekeeping playbook');

  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth);
  if (overflow) throw Error('mobile horizontal overflow');
  await page.screenshot({ path: 'qa-keystone-current-priority-mobile.png', fullPage: true });

  await page.getByRole('button', { name: 'Completed' }).click();
  if (!(await page.locator('#novaire-keystone-streak').innerText()).includes('1 day')) throw Error('streak did not increment');
  await page.reload();
  if (!(await page.locator('#novaire-keystone-streak').innerText()).includes('1 day')) throw Error('streak did not persist');

  console.log('PASS: exact-priority action, intent tailoring, OS cleanup classification, Ricies continuity, Enter reset, persistence, mobile overflow');
  await browser.close();
})().catch(error => { console.error(error); process.exit(1); });
