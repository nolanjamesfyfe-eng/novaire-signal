const { chromium } = require('/root/clawd/novaire-operations-system/node_modules/playwright');
const assert = require('node:assert/strict');
const url = (process.env.PORTFOLIO_URL || 'http://127.0.0.1:8765/portfolio/index.html') + `?qa=${Date.now()}`;

async function arcPoint(slice) {
  return slice.evaluate((node) => {
    const svg = node.ownerSVGElement;
    const slices = [...svg.querySelectorAll('.allocation-slice')];
    const values = slices.map((item) => Number(item.dataset.percent));
    const index = slices.indexOf(node);
    const total = values.reduce((sum, value) => sum + value, 0);
    const before = values.slice(0, index).reduce((sum, value) => sum + value, 0);
    const angle = (-90 + ((before + values[index] / 2) / total) * 360) * Math.PI / 180;
    const point = svg.createSVGPoint();
    point.x = 160 + 108 * Math.cos(angle);
    point.y = 160 + 108 * Math.sin(angle);
    const screen = point.matrixTransform(svg.getScreenCTM());
    return { x: screen.x, y: screen.y };
  });
}

async function verifySection(page, section, name, mobile) {
  await section.scrollIntoViewIfNeeded();
  const slices = section.locator('.allocation-slice');
  const items = section.locator('.legend-item');
  const expected = await items.evaluateAll((nodes) => nodes.map((node) => ({
    sector: node.dataset.allocationSector,
    pct: node.dataset.displayPercent,
  })));
  assert(expected.length > 0, `${name} must have Sheet-backed allocations`);
  assert.equal(await slices.count(), expected.length, `${name} slice and legend counts`);
  if (mobile) {
    for (const target of [slices.first(), items.first()]) {
      const styles = await target.evaluate((node) => {
        const style = getComputedStyle(node);
        return { tapHighlight: style.webkitTapHighlightColor, touchAction: style.touchAction };
      });
      assert.equal(styles.tapHighlight, 'rgba(0, 0, 0, 0)', `${name} suppresses native full-element tap flash`);
      assert.equal(styles.touchAction, 'manipulation', `${name} uses immediate touch interaction`);
    }
  }
  for (let index = 0; index < expected.length; index += 1) {
    const slice = slices.nth(index);
    const item = items.nth(index);
    const value = expected[index];
    const point = await arcPoint(slice);
    if (mobile) await page.touchscreen.tap(point.x, point.y);
    else await page.mouse.move(point.x, point.y);
    assert.equal(await section.locator('.allocation-core-kicker').textContent(), value.sector, `${name} real arc pointer symbol/sector`);
    assert.equal(await section.locator('.allocation-core-label').textContent(), value.pct, `${name} real arc pointer percentage`);
    assert(await slice.evaluate((node) => node.classList.contains('is-active')), `${name} arc active`);
    assert(await item.evaluate((node) => node.classList.contains('is-active')), `${name} synchronized legend`);
    await item.focus();
    assert.equal(await section.locator('.allocation-core-kicker').textContent(), value.sector, `${name} legend keyboard focus`);
    assert.equal(await section.locator('.allocation-core-label').textContent(), value.pct, `${name} legend focus percentage`);
    if (mobile) await page.locator('body').dispatchEvent('pointerdown');
  }
  const firstSlice = slices.first();
  await firstSlice.focus();
  await firstSlice.press('Enter');
  assert.equal(await section.locator('.allocation-core-kicker').textContent(), expected[0].sector, `${name} keyboard Enter`);
  assert(await items.first().evaluate((node) => node.classList.contains('is-active')), `${name} keyboard legend sync`);
  await firstSlice.press('Escape');
  assert.equal(await section.locator('.allocation-core-kicker').textContent(), await section.locator('.allocation-core-kicker').getAttribute('data-allocation-default'), `${name} Escape reset`);
  const box = await section.boundingBox();
  const viewport = page.viewportSize();
  assert(box.x >= 0 && box.x + box.width <= viewport.width + 1, `${name} viewport bounds`);
}

(async () => {
  const browser = await chromium.launch({ headless: true, executablePath: '/snap/bin/chromium', args: ['--no-sandbox'] });
  try {
    for (const viewport of [{ name: 'desktop', width: 1280, height: 900, mobile: false }, { name: 'mobile', width: 390, height: 844, mobile: true }]) {
      const page = await browser.newPage({ viewport: { width: viewport.width, height: viewport.height }, hasTouch: viewport.mobile, isMobile: viewport.mobile });
      await page.goto(url, { waitUntil: 'networkidle' });
      const sections = page.locator('.allocation-section');
      assert.equal(await sections.count(), 2, 'both portfolio and Kraken charts must render');
      await verifySection(page, sections.nth(0), 'portfolio allocation', viewport.mobile);
      await verifySection(page, sections.nth(1), 'Kraken weighting', viewport.mobile);
      await page.screenshot({ path: `qa-artifacts/allocation-donut-both-${viewport.name}.png`, fullPage: true });
      await page.close();
    }
  } finally {
    await browser.close();
  }
  console.log('Verified both Sheet-backed charts via real arc pointer hover/tap, synchronized legend, keyboard, reset, and viewport bounds.');
})().catch((error) => { console.error(error); process.exit(1); });
