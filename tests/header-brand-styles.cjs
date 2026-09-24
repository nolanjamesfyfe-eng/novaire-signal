const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require('/root/clawd/novaire-operations-system/node_modules/playwright');

(async () => {
  const browser = await chromium.launch({ headless: true, executablePath: '/snap/bin/chromium', args: ['--no-sandbox'] });
  const html = fs.readFileSync(path.resolve(__dirname, '..', 'index.html'), 'utf8');
  try {
    for (const viewport of [{ width: 1280, height: 900 }, { width: 390, height: 844 }]) {
      const page = await browser.newPage({ viewport });
      await page.setContent(html, { waitUntil: 'load' });
      const styles = await page.evaluate(() => {
        const wordmark = document.querySelector('.header-brand .signal-wordmark');
        const signal = wordmark.querySelector(':scope > span');
        const date = document.querySelector('.dateline .date');
        const globe = document.querySelector('.header-brand .signal-map').getBoundingClientRect();
        const text = wordmark.getBoundingClientRect();
        const bolt = document.querySelector('.header-brand .signal-bolt').getBoundingClientRect();
        const logo = document.querySelector('.header-brand .footer-logo');
        const pick = (el) => { const style = getComputedStyle(el); return { color: style.color, fontStyle: style.fontStyle }; };
        return {
          novaire: pick(wordmark), signal: pick(signal), date: pick(date),
          gap: getComputedStyle(logo).gap,
          iconSlotWidths: { globe: globe.width, bolt: bolt.width },
        };
      });
      assert.deepEqual(styles.novaire, { color: 'rgb(240, 238, 248)', fontStyle: 'normal' });
      assert.deepEqual(styles.signal, { color: 'rgb(181, 150, 98)', fontStyle: 'italic' });
      assert.equal(styles.date.color, 'rgb(240, 238, 248)');
      assert.equal(styles.gap, '12px');
      assert.ok(Math.abs(styles.iconSlotWidths.globe - styles.iconSlotWidths.bolt) < 0.1, JSON.stringify(styles.iconSlotWidths));
      await page.close();
    }
  } finally { await browser.close(); }
  console.log('Header computed styles and equal 12px gaps verified at desktop and mobile viewports.');
})().catch((error) => { console.error(error); process.exit(1); });