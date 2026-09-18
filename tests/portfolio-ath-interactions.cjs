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
    const ath = Math.max(...series.map(point => point.cad));
    const latest = series.at(-1);
    const change = hero.locator('.tracker-hero-change');
    const value = hero.locator('.tracker-hero-value');
    assert.equal(await change.textContent(), athText(latest.cad, ath));
    assert.equal(await hero.locator('.tracker-range.is-active').getAttribute('data-range'), 'YTD');

    await hero.locator('[data-range="ALL"]').click();
    assert.equal(await change.textContent(), athText(latest.cad, ath));
    const box = await hero.locator('svg').boundingBox();
    assert.ok(box);
    const peakIndex = series.findIndex(point => point.cad === ath);
    const lowerIndex = series.reduce((best, point, index) => point.cad < series[best].cad ? index : best, 0);
    const hoverIndex = async index => {
      const chartX = 18 + (920 - 36) * index / Math.max(series.length - 1, 1);
      await page.mouse.move(box.x + chartX / 920 * box.width, box.y + box.height / 2);
    };

    await hoverIndex(lowerIndex);
    assert.equal(await value.textContent(), `C$${series[lowerIndex].cad.toLocaleString('en-CA', {minimumFractionDigits: 2, maximumFractionDigits: 2})}`);
    assert.equal(await change.textContent(), athText(series[lowerIndex].cad, ath));

    await hoverIndex(peakIndex);
    assert.equal(await value.textContent(), `C$${ath.toLocaleString('en-CA', {minimumFractionDigits: 2, maximumFractionDigits: 2})}`);
    assert.equal(await change.textContent(), 'C$0 (0.00%) · ATH');

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
