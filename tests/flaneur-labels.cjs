const { test } = require('node:test');
const assert = require('node:assert/strict');
const { chromium } = require('/root/clawd/novaire-operations-system/node_modules/playwright');
const fs = require('fs');

const base = process.env.FLANEUR_URL || 'http://127.0.0.1:8765/map/index.html';
const artifacts = process.env.FLANEUR_ARTIFACTS || '/root/clawd/artifacts/flaneur-geography-labels';
fs.mkdirSync(artifacts, { recursive: true });

async function open(viewport, mobile = false) {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport, hasTouch: mobile, isMobile: mobile });
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.goto(base, { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('#globe-canvas[data-ready="true"]');
  return { browser, page, errors };
}

for (const [name, viewport, mobile] of [
  ['desktop', { width: 1440, height: 1000 }, false],
  ['mobile', { width: 390, height: 844 }, true],
]) test(`${name} globe renders overview labels and zoom-aware waterways`, async () => {
  const { browser, page, errors } = await open(viewport, mobile);
  try {
    const canvas = page.locator('#globe-canvas');
    const overview = await canvas.evaluate(node => ({
      continents: Number(node.dataset.labelContinents),
      oceans: Number(node.dataset.labelOceans),
      waterways: Number(node.dataset.labelWaterways),
      labels: node.dataset.labels,
      zoom: Number(node.dataset.zoom),
    }));
    assert.equal(overview.zoom, 1);
    assert.ok(overview.continents >= 2, JSON.stringify(overview));
    assert.ok(overview.oceans >= 1, JSON.stringify(overview));
    assert.equal(overview.waterways, 0, JSON.stringify(overview));
    await page.screenshot({ path: `${artifacts}/${name}-overview.png`, fullPage: true });

    await page.fill('#search', 'Egypt');
    await page.locator('.country-row[data-code="EG"]').click();
    await canvas.evaluate(node => {
      node.dispatchEvent(new KeyboardEvent('keydown', { key: '+', bubbles: true }));
      node.dispatchEvent(new KeyboardEvent('keydown', { key: '+', bubbles: true }));
    });
    await page.waitForTimeout(100);
    const zoomed = await canvas.evaluate(node => ({
      continents: Number(node.dataset.labelContinents),
      oceans: Number(node.dataset.labelOceans),
      waterways: Number(node.dataset.labelWaterways),
      labels: node.dataset.labels,
      zoom: Number(node.dataset.zoom),
    }));
    assert.ok(zoomed.zoom >= 3, JSON.stringify(zoomed));
    assert.equal(zoomed.continents, 0, JSON.stringify(zoomed));
    assert.ok(zoomed.waterways >= 1, JSON.stringify(zoomed));
    assert.match(zoomed.labels, /Suez Canal/, JSON.stringify(zoomed));
    assert.ok(zoomed.oceans >= 1, JSON.stringify(zoomed));
    await page.locator('#tooltip').evaluate(node => node.classList.remove('show'));
    await page.screenshot({ path: `${artifacts}/${name}-zoom.png`, fullPage: true });
    assert.deepEqual(errors, []);
  } finally {
    await browser.close();
  }
});
