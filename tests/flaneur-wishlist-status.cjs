const { test } = require('node:test');
const assert = require('node:assert/strict');
const { chromium } = require('/root/clawd/novaire-operations-system/node_modules/playwright');

const base = process.env.FLANEUR_URL || 'http://127.0.0.1:8765/map/index.html';
const key = 'novaire.flaneur.wishlist.v1';

test('only saved wishlist top five are orange; reorder, visited precedence and reload stay correct', async () => {
  const browser = await chromium.launch({headless: true});
  const context = await browser.newContext({viewport:{width:390,height:844},hasTouch:true,isMobile:true});
  await context.addInitScript(({key}) => {
    if (!sessionStorage.getItem('wishlist-test-seeded')) {
      localStorage.setItem(key, JSON.stringify({version:1,codes:['JP','AR','CL','BR','IS','PT'],locked:false}));
      sessionStorage.setItem('wishlist-test-seeded','true');
    }
  }, {key});
  const page = await context.newPage();
  try {
    await page.goto(base, {waitUntil:'domcontentloaded'});
    await page.waitForSelector('#globe-canvas[data-ready="true"]');
    await page.waitForFunction(() => document.querySelector('#wishlist-title')?.textContent === 'Top 6 countries to visit');

    assert.equal(await page.locator('.legend').textContent().then(text => text.includes('Future visits')), true);
    assert.deepEqual(await page.evaluate(() => {
      const style=getComputedStyle(document.documentElement);
      return [style.getPropertyValue('--visited').trim(),style.getPropertyValue('--upcoming').trim()];
    }), ['#208a4e','#bf6d2a']);
    assert.deepEqual(await page.evaluate(async () => (await (await fetch('/map/visited.json')).json()).planned), []);

    await page.fill('#search','Japan');
    const japan=page.locator('.country-row[data-code="JP"]');
    assert.equal(await japan.locator('span').last().innerText(),'VISITED');
    assert.equal(await japan.getAttribute('class'),'country-row yes');

    await page.fill('#search','Argentina');
    const argentina=page.locator('.country-row[data-code="AR"]');
    assert.equal(await argentina.locator('span').last().innerText(),'WANT TO VISIT');
    assert.equal(await argentina.getAttribute('class'),'country-row calling');

    await page.fill('#search','Portugal');
    const portugal=page.locator('.country-row[data-code="PT"]');
    assert.equal(await portugal.locator('span').last().innerText(),'NOT VISITED','sixth rank is not orange');
    assert.equal(await portugal.evaluate(row => row.classList.contains('calling')),false);

    await page.locator('#wishlist-list [data-code="PT"] [data-action="up"]').click();
    await page.fill('#search','Portugal');
    assert.equal(await page.locator('.country-row[data-code="PT"] span').last().innerText(),'WANT TO VISIT','new fifth rank recolors immediately');
    assert.equal(await page.locator('.country-row[data-code="PT"]').getAttribute('class'),'country-row calling');
    await page.fill('#search','Iceland');
    assert.equal(await page.locator('.country-row[data-code="IS"] span').last().innerText(),'NOT VISITED','country moved to sixth immediately loses orange');
    assert.equal(await page.locator('.country-row[data-code="IS"]').evaluate(row => row.classList.contains('calling')),false);

    await page.reload({waitUntil:'domcontentloaded'});
    await page.waitForSelector('#globe-canvas[data-ready="true"]');
    await page.waitForFunction(() => document.querySelector('#wishlist-title')?.textContent === 'Top 6 countries to visit');
    assert.deepEqual(await page.evaluate(key => JSON.parse(localStorage.getItem(key)).codes, key), ['JP','AR','CL','BR','PT','IS']);
    await page.fill('#search','Portugal');
    assert.equal(await page.locator('.country-row[data-code="PT"] span').last().innerText(),'WANT TO VISIT','saved fifth rank remains orange after reload');
    await page.fill('#search','Iceland');
    assert.equal(await page.locator('.country-row[data-code="IS"] span').last().innerText(),'NOT VISITED','saved sixth rank remains non-orange after reload');
  } finally {
    await browser.close();
  }
});