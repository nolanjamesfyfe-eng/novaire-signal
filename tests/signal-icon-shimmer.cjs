const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require('/root/clawd/novaire-operations-system/node_modules/playwright');

const html = fs.readFileSync(path.resolve(__dirname, '..', 'index.html'), 'utf8');
const roots = ['.header-brand', '.footer'];
const icons = ['.signal-map-icon', '.signal-bolt-icon'];

(async () => {
  const browser = await chromium.launch({ headless: true, executablePath: '/snap/bin/chromium', args: ['--no-sandbox'] });
  try {
    for (const viewport of [{ width: 1280, height: 900 }, { width: 390, height: 844 }]) {
      const page = await browser.newPage({ viewport });
      await page.setContent(html, { waitUntil: 'load' });
      await page.evaluate(() => document.fonts.ready);
      const result = await page.evaluate(({ roots, icons }) => {
        const targets = roots.flatMap(root => icons.map(icon => document.querySelector(`${root} ${icon}`)));
        const snapshot = () => targets.map(el => {
          const r = el.getBoundingClientRect();
          const s = getComputedStyle(el);
          return { x: r.x, y: r.y, width: r.width, height: r.height, filter: s.filter, opacity: s.opacity };
        });
        const animations = targets.map(el => el.getAnimations()[0]);
        animations.forEach(animation => { animation.pause(); animation.currentTime = 0; });
        const phase0 = snapshot();
        animations.forEach(animation => { animation.currentTime = 1748; });
        const phase1 = snapshot();
        const paintBottom = el => {
          const box = el.getBBox();
          const matrix = el.getScreenCTM();
          return new DOMPoint(box.x + box.width, box.y + box.height).matrixTransform(matrix).y;
        };
        return {
          phase0, phase1,
          bottomDeltas: roots.map(root => Math.abs(
            paintBottom(document.querySelector(`${root} .signal-map-icon`)) -
            paintBottom(document.querySelector(`${root} .signal-bolt-icon`))
          )),
          gaps: roots.map(root => getComputedStyle(document.querySelector(`${root} .footer-logo`)).gap),
          overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
        };
      }, { roots, icons });
      result.phase0.forEach((first, index) => {
        const second = result.phase1[index];
        assert.notEqual(first.filter, second.filter, `light did not shimmer: ${viewport.width}px icon ${index}`);
        for (const key of ['x', 'y', 'width', 'height']) assert.ok(Math.abs(first[key] - second[key]) < 0.01, `layout moved: ${viewport.width}px icon ${index} ${key}`);
      });
      result.bottomDeltas.forEach(delta => assert.ok(delta < 0.15, `painted bottoms differ by ${delta}px at ${viewport.width}px`));
      assert.deepEqual(result.gaps, ['12px', '12px']);
      assert.ok(result.overflow <= 0, `horizontal overflow at ${viewport.width}px`);
      await page.close();
    }

    const reduced = await browser.newPage({ viewport: { width: 390, height: 844 }, reducedMotion: 'reduce' });
    await reduced.setContent(html, { waitUntil: 'load' });
    const reducedStyles = await reduced.evaluate(({ roots, icons }) => roots.flatMap(root => icons.map(icon => {
      const s = getComputedStyle(document.querySelector(`${root} ${icon}`));
      return { animation: s.animationName, filter: s.filter, opacity: s.opacity };
    })), { roots, icons });
    reducedStyles.forEach(style => {
      assert.equal(style.animation, 'none');
      assert.match(style.filter, /brightness\(1\.12\).*drop-shadow/);
      assert.equal(style.opacity, '1');
    });
    await reduced.close();
  } finally {
    await browser.close();
  }
  console.log('Header/footer shimmer changes light without layout movement; painted bottoms, mobile fit, and reduced motion verified.');
})().catch(error => { console.error(error); process.exit(1); });
