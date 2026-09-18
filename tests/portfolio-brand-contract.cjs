const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require('/root/clawd/novaire-operations-system/node_modules/playwright');

const root = path.resolve(__dirname, '..');
const homepage = fs.readFileSync(path.join(root, 'index.html'), 'utf8');
const portfolio = fs.readFileSync(path.join(root, 'portfolio/index.html'), 'utf8');

(async () => {
  assert.ok(!portfolio.includes('Back to Signal'), 'legacy upper-left link remains');
  const browser = await chromium.launch({ headless: true, executablePath: '/snap/bin/chromium', args: ['--no-sandbox'] });
  try {
    for (const viewport of [{ name: 'desktop', width: 1280, height: 900 }, { name: 'mobile', width: 390, height: 844 }]) {
      const homePage = await browser.newPage({ viewport });
      const page = await browser.newPage({ viewport });
      await homePage.setContent(homepage, { waitUntil: 'load' });
      await page.setContent(portfolio, { waitUntil: 'load' });
      await Promise.all([homePage.evaluate(() => document.fonts.ready), page.evaluate(() => document.fonts.ready)]);

      const inspect = async p => p.evaluate(() => {
        const rows = ['.header-brand', '.footer'].map(root => {
          const node = document.querySelector(root);
          const map = node.querySelector('.signal-map');
          const wordmark = node.querySelector('.signal-wordmark');
          const signal = wordmark.querySelector(':scope > span');
          const bolt = node.querySelector('.signal-bolt');
          const mapIcon = map.querySelector('.signal-map-icon');
          const boltIcon = bolt.querySelector('.signal-bolt-icon');
          const style = el => { const s = getComputedStyle(el); return { color: s.color, fontStyle: s.fontStyle, fontFamily: s.fontFamily, fontSize: s.fontSize, fontWeight: s.fontWeight, letterSpacing: s.letterSpacing }; };
          const animation = el => { const s = getComputedStyle(el); return { name: s.animationName, duration: s.animationDuration, timing: s.animationTimingFunction, delay: s.animationDelay }; };
          return {
            hrefs: [map.getAttribute('href'), wordmark.getAttribute('href'), bolt.getAttribute('href')],
            wordmark: style(wordmark), signal: style(signal), gap: getComputedStyle(node.querySelector('.signal-brand-row')).gap,
            animation: [animation(mapIcon), animation(boltIcon)],
            svg: [mapIcon.outerHTML, boltIcon.outerHTML],
          };
        });
        return { rows, overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth };
      });
      const [home, result] = await Promise.all([inspect(homePage), inspect(page)]);
      for (let i = 0; i < 2; i++) {
        assert.deepEqual(result.rows[i].svg, home.rows[i].svg, `${viewport.name} row ${i} artwork differs`);
        assert.deepEqual(result.rows[i].wordmark, home.rows[i].wordmark, `${viewport.name} row ${i} wordmark differs`);
        assert.deepEqual(result.rows[i].signal, home.rows[i].signal, `${viewport.name} row ${i} SIGNAL differs`);
        assert.equal(result.rows[i].gap, home.rows[i].gap);
        assert.deepEqual(result.rows[i].animation, home.rows[i].animation, `${viewport.name} row ${i} animation differs`);
        assert.deepEqual(result.rows[i].hrefs, ['/flaneur', '/', '/portfolio/']);
        assert.equal(result.rows[i].wordmark.color, 'rgb(240, 238, 248)');
        assert.equal(result.rows[i].wordmark.fontStyle, 'normal');
        assert.equal(result.rows[i].signal.color, 'rgb(181, 150, 98)');
        assert.equal(result.rows[i].signal.fontStyle, 'italic');
        assert.equal(result.rows[i].gap, '12px');
      }
      assert.ok(result.overflow <= 0, `${viewport.name} horizontal overflow`);
      const links = page.locator('.header-brand .signal-brand-row > a, .footer .signal-brand-row > a');
      assert.equal(await links.count(), 6);
      for (let i = 0; i < 6; i++) { await links.nth(i).focus(); assert.equal(await links.nth(i).evaluate(el => document.activeElement === el), true); }
      await page.screenshot({ path: path.join(root, `qa-artifacts/portfolio-brand-${viewport.name}.png`), fullPage: true });
      await Promise.all([homePage.close(), page.close()]);
    }

    const reduced = await browser.newPage({ viewport: { width: 390, height: 844 }, reducedMotion: 'reduce' });
    await reduced.setContent(portfolio, { waitUntil: 'load' });
    const reducedAnimations = await reduced.locator('.signal-map-icon,.signal-bolt-icon').evaluateAll(nodes => nodes.map(el => ({ animation: getComputedStyle(el).animationName, filter: getComputedStyle(el).filter })));
    reducedAnimations.forEach(item => { assert.equal(item.animation, 'none'); assert.match(item.filter, /brightness\(1\.12\).*drop-shadow/); });
    await reduced.close();
  } finally { await browser.close(); }
  console.log('Portfolio header/footer exactly match homepage artwork, typography, spacing, pulse, reduced motion, links, keyboard focus, and mobile fit.');
})().catch(error => { console.error(error); process.exit(1); });
