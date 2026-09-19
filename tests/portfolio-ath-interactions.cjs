const { chromium } = require('/root/clawd/novaire-operations-system/node_modules/playwright');
const assert = require('node:assert/strict');

const url = process.env.PORTFOLIO_URL || 'http://127.0.0.1:8765/portfolio/index.html';
const money = value => `C$${Math.abs(value).toLocaleString('en-CA', {maximumFractionDigits: 0})}`;
const athText = (value, ath) => {
  const delta = value - ath;
  const sign = delta < 0 ? '−' : delta > 0 ? '+' : '';
  const pct = ath ? delta / ath * 100 : 0;
  return `${sign ? sign + ' ' : ''}${money(delta)} (${sign}${Math.abs(pct).toFixed(2)}%) · ATH`;
};

(async () => {
  const browser = await chromium.launch({headless: true, executablePath: '/snap/bin/chromium', args: ['--no-sandbox']});
  try {
    const page = await browser.newPage({viewport: {width: 1280, height: 900}});
    await page.goto(url, {waitUntil: 'networkidle'});
    const hero = page.locator('.tracker-hero');
    const series = JSON.parse(await hero.getAttribute('data-series'));
    const ath = Number(await hero.getAttribute('data-ath-cad'));
    assert.equal(await hero.getAttribute('data-ath-source'), 'Google Sheet · TFSA/WS · ATH row');
    const latest = series.at(-1);
    const change = hero.locator('.tracker-hero-change');
    const value = hero.locator('.tracker-hero-value');
    assert.equal(await change.textContent(), athText(latest.cad, ath));
    assert.equal(await hero.locator('.tracker-range.is-active').getAttribute('data-range'), 'YTD');
    const tracker = page.locator('#net-worth-tracker');
    assert.equal(await tracker.getByText('Google Sheet daily closes · active accounts', {exact: true}).count(), 0);
    assert.equal(await tracker.getByText('Combined Net Worth', {exact: true}).count(), 0);
    assert.equal(await tracker.locator('.tracker-total').count(), 0);
    assert.equal(await tracker.locator('.tracker-hero-value').count(), 1);

    for (const viewport of [{width: 1280, height: 900}, {width: 390, height: 844}]) {
      await page.setViewportSize(viewport);
      const active = hero.locator('.tracker-range.is-active');
      const geometry = await active.evaluate(el => {
        const pseudo = getComputedStyle(el, '::before');
        const box = el.getBoundingClientRect();
        return {width: parseFloat(pseudo.width), height: parseFloat(pseudo.height), center: box.left + box.width / 2};
      });
      assert.ok(Math.abs(geometry.width - geometry.height) < 0.05, JSON.stringify(geometry));
      assert.ok(Math.abs(geometry.width - 32) < 0.05, JSON.stringify(geometry));
    }

    await hero.locator('[data-range="ALL"]').click();
    assert.equal(await change.textContent(), athText(latest.cad, ath));
    const box = await hero.locator('svg').boundingBox();
    assert.ok(box);
    const lowerIndex = series.reduce((best, point, index) => point.cad < series[best].cad ? index : best, 0);
    const hoverIndex = async index => {
      const chartX = 18 + (920 - 36) * index / Math.max(series.length - 1, 1);
      await page.mouse.move(box.x + chartX / 920 * box.width, box.y + box.height / 2);
    };

    await hoverIndex(lowerIndex);
    assert.equal(await value.textContent(), `C$${series[lowerIndex].cad.toLocaleString('en-CA', {minimumFractionDigits: 2, maximumFractionDigits: 2})}`);
    assert.equal(await change.textContent(), athText(series[lowerIndex].cad, ath));
    const dotBox = await hero.locator('.tracker-dot').boundingBox();
    assert.ok(dotBox);
    assert.ok(Math.abs(dotBox.width - dotBox.height) < 0.25, JSON.stringify(dotBox));

    await page.mouse.move(box.x - 10, box.y - 10);
    assert.equal(await value.textContent(), `C$${latest.cad.toLocaleString('en-CA', {minimumFractionDigits: 2, maximumFractionDigits: 2})}`);
    assert.equal(await change.textContent(), athText(latest.cad, ath));

    for (const range of ['1M', 'YTD', '1D']) {
      await hero.locator(`[data-range="${range}"]`).click();
      assert.equal(await change.textContent(), athText(latest.cad, ath));
    }
    console.log(JSON.stringify({points: series.length, ath, latest: latest.cad, lower: series[lowerIndex].cad, testedRanges: ['ALL', '1M', 'YTD', '1D']}));
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exit(1); });
