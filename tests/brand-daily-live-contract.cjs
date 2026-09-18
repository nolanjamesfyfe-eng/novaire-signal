const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require('/root/clawd/novaire-operations-system/node_modules/playwright');

const root = path.resolve(__dirname, '..');
const pages = [
  ['home', 'index.html'],
  ['daily', 'portfolio/daily/index.html'],
];
const evidence = path.join(root, 'qa-artifacts', 'brand-daily');
fs.mkdirSync(evidence, { recursive: true });

(async () => {
  const browser = await chromium.launch({ headless: true, executablePath: '/snap/bin/chromium', args: ['--no-sandbox'] });
  const report = {};
  try {
    for (const viewport of [{ name: 'desktop', width: 1280, height: 900 }, { name: 'mobile', width: 390, height: 844 }]) {
      report[viewport.name] = {};
      for (const [name, file] of pages) {
        const page = await browser.newPage({ viewport });
        await page.setContent(fs.readFileSync(path.join(root, file), 'utf8'), { waitUntil: 'load' });
        const result = await page.evaluate(() => {
          const row = document.querySelector('.header-brand .signal-brand-row, .daily-header .signal-brand-row');
          const wordmark = row.querySelector('.signal-wordmark');
          const signal = wordmark.querySelector(':scope > span');
          const globe = row.querySelector('.signal-map-icon');
          const bolt = row.querySelector('.signal-bolt-icon');
          const rs = getComputedStyle(row), ws = getComputedStyle(wordmark), ss = getComputedStyle(signal);
          const gs = getComputedStyle(globe), bs = getComputedStyle(bolt), rect = row.getBoundingClientRect();
          const title = document.querySelector('.daily-title');
          const content = title || document.querySelector('.dateline');
          return {
            fontSize: rs.fontSize, centerDelta: Math.abs((rect.left + rect.width / 2) - innerWidth / 2),
            brandToContentGap: content ? content.getBoundingClientRect().top - rect.bottom : null,
            novaireColor: ws.color, novaireStyle: ws.fontStyle, signalColor: ss.color, signalStyle: ss.fontStyle,
            globeAnimation: gs.animationName, boltAnimation: bs.animationName,
            globeDelay: gs.animationDelay, boltDelay: bs.animationDelay,
            title: title && { color: getComputedStyle(title).color, family: getComputedStyle(title).fontFamily, top: title.getBoundingClientRect().top, brandBottom: rect.bottom },
            geo: document.body.textContent.includes('Geopolitical pressure'), newsLinks: [...document.querySelectorAll('.story a')].length,
          };
        });
        const expectedFontSize = viewport.name === 'desktop' ? '31.68px' : '28.8px';
        assert.equal(result.fontSize, expectedFontSize, `${name}/${viewport.name} font size`);
        assert.ok(result.centerDelta < 25, `${name}/${viewport.name} centered: ${result.centerDelta}`);
        assert.equal(result.novaireColor, 'rgb(240, 238, 248)');
        assert.equal(result.novaireStyle, 'normal');
        assert.equal(result.signalColor, 'rgb(181, 150, 98)');
        assert.equal(result.signalStyle, 'italic');
        assert.equal(result.globeAnimation, 'signal-gold-shimmer');
        assert.equal(result.boltAnimation, 'signal-gold-shimmer');
        assert.equal(result.globeDelay, '-0.72s');
        assert.equal(result.boltDelay, '0s');
        if (name === 'daily') {
          assert.equal(result.title.color, 'rgb(255, 255, 255)');
          assert.match(result.title.family, /Inter|system-ui/);
          assert.ok(result.title.top - result.title.brandBottom >= 40);
          assert.equal(result.geo, false);
          assert.equal(result.newsLinks, 0);
        }
        report[viewport.name][name] = result;
        await page.screenshot({ path: path.join(evidence, `${name}-${viewport.name}.png`), fullPage: true });
        await page.close();
      }
      const spacingDelta = Math.abs(report[viewport.name].daily.brandToContentGap - report[viewport.name].home.brandToContentGap);
      assert.ok(spacingDelta < 0.1, `daily/${viewport.name} uses homepage brand-to-content spacing: ${spacingDelta}`);
    }
  } finally { await browser.close(); }
  fs.writeFileSync(path.join(evidence, 'computed-contract.json'), JSON.stringify(report, null, 2));
  console.log(`Brand/Daily computed contract verified; evidence: ${evidence}`);
})().catch(error => { console.error(error); process.exit(1); });
