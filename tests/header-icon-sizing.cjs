const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require('/root/clawd/novaire-operations-system/node_modules/playwright');

(async () => {
  const html = fs.readFileSync(path.resolve(__dirname, '..', 'index.html'), 'utf8');
  const browser = await chromium.launch({ headless: true, executablePath: '/snap/bin/chromium', args: ['--no-sandbox'] });
  try {
    for (const viewport of [{ width: 1280, height: 900 }, { width: 390, height: 844 }]) {
      const page = await browser.newPage({ viewport });
      await page.setContent(html, { waitUntil: 'load' });
      await page.evaluate(() => document.fonts.ready);
      const result = await page.evaluate(() => {
        const rect = (selector) => {
          const r = document.querySelector(selector).getBoundingClientRect();
          return { left: r.left, right: r.right, width: r.width };
        };
        const globe = rect('.header-brand .signal-map-icon');
        const globeSlot = rect('.header-brand .signal-map');
        const wordmark = rect('.header-brand .signal-wordmark');
        const bolt = rect('.header-brand .signal-bolt-icon');
        const boltSlot = rect('.header-brand .signal-bolt');
        return {
          globe, globeSlot, wordmark, bolt, boltSlot,
          declaredGap: getComputedStyle(document.querySelector('.header-brand .footer-logo')).gap,
          overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
        };
      });
      assert.ok(Math.abs(result.globeSlot.width - result.boltSlot.width) < 0.1, JSON.stringify(result));
      assert.equal(result.declaredGap, '12px');
      assert.ok(Math.abs(result.globe.width / result.globeSlot.width - 1) < 0.01, JSON.stringify(result));
      assert.ok(result.bolt.width < result.boltSlot.width, JSON.stringify(result));
      assert.ok(result.overflow <= 0, JSON.stringify(result));
      await page.close();
    }
  } finally {
    await browser.close();
  }
  console.log('Exact header icon sizing, declared 12px spacing, equal slots, and mobile fit verified.');
})().catch((error) => { console.error(error); process.exit(1); });