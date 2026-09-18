const { test } = require('node:test');
const assert = require('node:assert/strict');
const { chromium } = require('/root/clawd/novaire-operations-system/node_modules/playwright');

const base = process.env.FLANEUR_URL || 'http://127.0.0.1:8765/map/index.html';

test('mobile globe silhouette fits and country taps work', async () => {
  const browser = await chromium.launch({headless: true});
  try {
    for (const width of [390, 600, 760]) {
      const page = await browser.newPage({viewport: {width, height: 844}, hasTouch: true});
      await page.goto(base, {waitUntil: 'networkidle'});
      await page.waitForSelector('.sphere');
      const geometry = await page.evaluate(() => {
        const sphere = document.querySelector('.sphere').getBBox();
        const svg = document.querySelector('#map').viewBox.baseVal;
        return {x:sphere.x,y:sphere.y,width:sphere.width,height:sphere.height,svgWidth:svg.width,svgHeight:svg.height};
      });
      assert.ok(geometry.x >= 0 && geometry.x + geometry.width <= geometry.svgWidth, `${width}px globe fits horizontally`);
      assert.ok(geometry.y >= 50 && geometry.y + geometry.height <= geometry.svgHeight - 40, `${width}px globe leaves legend and hint room`);
      if (width === 390) assert.ok(Math.abs(geometry.width - 374) < 0.1, '390px approved diameter remains exactly 374px');

      const point = await page.locator('.country').evaluateAll(nodes => {
        const hit = nodes.find(n => { const b=n.getBoundingClientRect(); return b.width>20 && b.height>20; });
        const b=hit.getBoundingClientRect(); return {x:b.x+b.width/2,y:b.y+b.height/2,code:hit.dataset.code};
      });
      await page.touchscreen.tap(point.x, point.y);
      await assert.doesNotReject(() => page.waitForSelector('.tooltip.show', {timeout: 1000}), `${width}px country tap opens tooltip`);
      await page.close();
    }
  } finally { await browser.close(); }
});

test('desktop zoom button keeps original 1.5 scale', async () => {
  const browser = await chromium.launch({headless: true});
  try {
    const page = await browser.newPage({viewport: {width: 1440, height: 1000}});
    await page.goto(base, {waitUntil: 'networkidle'});
    await page.waitForSelector('.country');
    await page.click('#zoom-in');
    await page.waitForTimeout(500);
    const transform = await page.locator('#map > g').getAttribute('transform');
    assert.match(transform, /scale\(1\.5\)/);
  } finally { await browser.close(); }
});