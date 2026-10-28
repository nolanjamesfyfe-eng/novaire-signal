#!/usr/bin/env node
'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const http = require('node:http');
const path = require('node:path');
const { chromium } = require('/root/clawd/novaire-operations-system/node_modules/playwright');

const ROOT = path.resolve(__dirname, '..');
const OUT = process.env.NOVAIRE_SIGNAL_ZH_QA_OUT || path.join(ROOT, 'qa-artifacts', 'zerohedge-card-parity');
const longTitle = '⚡ ' + 'A sourced ZeroHedge headline tests the longest safe title boundary ' .repeat(4) + '終';
const longExcerpt = 'The original publisher excerpt remains sourced while this defensive layout fixture verifies the footer and content boundary. '.repeat(4) + '終';
const article = (n, extra = {}) => ({
  title: `${longTitle} ${n}`,
  excerpt: `${longExcerpt} ${n}`,
  url: `https://www.zerohedge.com/markets/layout-fixture-${n}`,
  publishedAt: 'Fri, 23 Oct 2026 09:00:00 +0000',
  image: 'https://assets.zerohedge.com/genuine-fixture.jpg',
  image_alt: 'Publisher image',
  ...extra,
});
const articles = [
  article(1),
  article(2, { image: '' }),
  article(3, { image: 'https://assets.zerohedge.com/broken-fixture.jpg' }),
  article(4, { image: 'https://cms.zerohedge.com/sites/default/files/cms-fixture.jpg' }),
  article(5, { image: '' }),
  article(6, { image: 'https://assets.zerohedge.com/broken-fixture.jpg' }),
];

function contentType(file) {
  if (file.endsWith('.html')) return 'text/html; charset=utf-8';
  if (file.endsWith('.json')) return 'application/json; charset=utf-8';
  if (file.endsWith('.svg')) return 'image/svg+xml';
  if (file.endsWith('.png')) return 'image/png';
  return 'application/octet-stream';
}

const server = http.createServer((req, res) => {
  const url = new URL(req.url, 'http://127.0.0.1');
  if (url.pathname === '/api/zerohedge') {
    setTimeout(() => {
      res.writeHead(200, { 'content-type': 'application/json; charset=utf-8', 'cache-control': 'no-store' });
      res.end(JSON.stringify({ ok: true, articles }));
    }, 500);
    return;
  }
  if (url.pathname.includes('broken-fixture.jpg')) {
    res.writeHead(404); res.end('broken'); return;
  }
  const rel = url.pathname === '/' ? 'index.html' : decodeURIComponent(url.pathname.slice(1));
  const file = path.resolve(ROOT, rel);
  if (!file.startsWith(ROOT + path.sep) || !fs.existsSync(file) || fs.statSync(file).isDirectory()) {
    res.writeHead(404); res.end('not found'); return;
  }
  res.writeHead(200, { 'content-type': contentType(file), 'cache-control': 'no-store' });
  fs.createReadStream(file).pipe(res);
});

function listen() {
  return new Promise(resolve => server.listen(0, '127.0.0.1', () => resolve(server.address().port)));
}

async function inspect(page, phase, viewport) {
  await page.waitForSelector('.signal-feed-card');
  await page.waitForSelector('#zerohedge-feed .zh-feed-card .feed-card-source');
  await page.locator('#zerohedge-feed').scrollIntoViewIfNeeded();
  await page.waitForTimeout(150);
  const result = await page.evaluate(() => {
    const rect = el => { const r = el.getBoundingClientRect(); return { x:r.x, y:r.y, width:r.width, height:r.height, top:r.top, right:r.right, bottom:r.bottom, left:r.left }; };
    const xCards = [...document.querySelectorAll('.signal-feed-card')].map(rect);
    const zhCards = [...document.querySelectorAll('#zerohedge-feed .zh-feed-card')].map(card => {
      const body = card.querySelector('.feed-card-body');
      const footer = card.querySelector('.feed-card-source');
      const title = card.querySelector('.feed-card-title');
      const excerpt = card.querySelector('.feed-card-excerpt');
      const cardRect = rect(card), bodyRect = rect(body), footerRect = rect(footer);
      return {
        card: cardRect, body: bodyRect, footer: footerRect,
        href: footer.href,
        pointerEvents: getComputedStyle(footer).pointerEvents,
        titleLength: Array.from(title.textContent).length,
        excerptLength: excerpt ? Array.from(excerpt.textContent).length : 0,
        titleRect: rect(title),
        excerptRect: excerpt ? rect(excerpt) : null,
        titleClamp: getComputedStyle(title).webkitLineClamp,
        excerptClamp: excerpt ? getComputedStyle(excerpt).webkitLineClamp : null,
        fullTitle: title.getAttribute('title'),
        ariaLabel: title.getAttribute('aria-label'),
        hasMedia: Boolean(card.querySelector('.feed-card-media')),
        header: rect(card.querySelector('.zh-story-header')),
        media: card.querySelector('.feed-card-media') ? rect(card.querySelector('.feed-card-media')) : null,
        excerptColor: excerpt ? getComputedStyle(excerpt).color : null,
        dimColor: getComputedStyle(card).getPropertyValue('--dim').trim(),
      };
    });
    return { xCards, zhCards };
  });
  for (let index = 0; index < result.zhCards.length; index++) {
    const card = page.locator('#zerohedge-feed .zh-feed-card').nth(index);
    await card.evaluate(el => el.scrollIntoView({ block: 'center', inline: 'center' }));
    await page.waitForTimeout(30);
    const footer = card.locator('.feed-card-source');
    await footer.click({ trial: true });
    result.zhCards[index].pointHitsFooter = true;
  }
  assert.equal(result.zhCards.length, 3, `${viewport} ${phase}: exactly three ZeroHedge cards`);
  assert.equal(result.xCards.length, 3, `${viewport} ${phase}: exactly three X cards`);
  const expectedClamps = ['4', '3'];
  for (const [index, item] of result.zhCards.entries()) {
    assert.ok(Math.abs(item.card.height - result.zhCards[0].card.height) < 1, 'Equal compact card geometry');
    assert.ok(Math.abs(item.footer.top - result.zhCards[0].footer.top) < 1, 'Source footer pinned across row');
    assert.ok(item.card.bottom - item.footer.bottom <= 11, 'No blank shell below footer');
    if (item.media) {
      assert.ok(item.titleRect.left >= item.media.right, 'Title beside genuine thumbnail');
      assert.ok(Math.abs(item.titleRect.top-item.media.top)<1, 'Title and image share header top');
    }
    if (item.excerptRect) {
      assert.ok(item.excerptRect.top >= item.header.bottom, 'Excerpt below whole header');
      assert.ok(Math.abs(item.excerptRect.width-item.body.width)<1, 'Excerpt uses full body width');
      assert.ok(item.excerptRect.top-item.header.bottom<=7, 'Compact header/excerpt spacing');
      const rgb = item.excerptColor.match(/\d+/g).map(Number);
      assert.ok(Math.max(...rgb)-Math.min(...rgb)<25, 'Excerpt is neutral gray');
    }
    assert.ok(item.footer.top >= item.card.top && item.footer.bottom <= item.card.bottom + 0.5, `${viewport} ${phase} card ${index}: footer inside card`);
    assert.ok(item.body.bottom <= item.footer.top + 0.5, `${viewport} ${phase} card ${index}: content does not overlap footer`);
    assert.ok(item.titleRect.bottom <= item.body.bottom + 0.5, `${viewport} ${phase} card ${index}: title inside content boundary`);
    if (item.excerptRect) assert.ok(item.excerptRect.bottom <= item.body.bottom + 0.5, `${viewport} ${phase} card ${index}: excerpt inside content boundary`);
    assert.match(item.href, /^https:\/\/(www\.)?zerohedge\.com\//, `${viewport} ${phase} card ${index}: genuine destination`);
    assert.equal(item.pointerEvents, 'auto', `${viewport} ${phase} card ${index}: footer is interactive`);
    assert.equal(item.pointHitsFooter, true, `${viewport} ${phase} card ${index}: no interaction cover`);
    assert.ok(item.titleLength <= 110, `${viewport} ${phase} card ${index}: title cap`);
    assert.ok(item.excerptLength <= 140, `${viewport} ${phase} card ${index}: excerpt cap`);
    assert.equal(item.titleClamp, expectedClamps[0], `${viewport} ${phase} card ${index}: defensive title clamp`);
    assert.equal(item.excerptClamp, expectedClamps[1], `${viewport} ${phase} card ${index}: defensive excerpt clamp`);
    assert.equal(item.ariaLabel, item.fullTitle, `${viewport} ${phase} card ${index}: accessible full title`);
  }
  return result;
}

(async () => {
  fs.mkdirSync(OUT, { recursive: true });
  const port = await listen();
  const browser = await chromium.launch({ headless: true, executablePath: process.env.CHROMIUM_PATH || '/snap/bin/chromium', args: ['--no-sandbox'] });
  const observations = [];
  try {
    for (const viewport of [{name:'desktop',width:1440,height:900},{name:'mobile-390',width:390,height:844},{name:'mobile-360',width:360,height:800}]) {
      const context = await browser.newContext({ viewport });
      const page = await context.newPage();
      await page.route(/^https:\/\/(assets|cms)\.zerohedge\.com\//, route => {
        if (route.request().url().includes('broken-fixture')) return route.fulfill({ status: 404, body: 'broken' });
        return route.fulfill({ status: 200, contentType: 'image/svg+xml', body: '<svg xmlns="http://www.w3.org/2000/svg" width="80" height="60"><rect width="80" height="60" fill="#b59662"/></svg>' });
      });
      await page.goto(`http://127.0.0.1:${port}/?layout=${viewport.name}`, { waitUntil: 'domcontentloaded' });
      const initial = await inspect(page, 'initial', viewport.name);
      await page.waitForFunction(() => document.getElementById('news-status')?.textContent.startsWith('3 of 6'));
      await page.waitForFunction(() => document.querySelectorAll('#zerohedge-feed .zh-feed-card').length === 3);
      const dynamicFirst = await inspect(page, 'dynamic-first', viewport.name);
      assert.deepEqual(dynamicFirst.zhCards.map(x => x.hasMedia), [true, false, false], `${viewport.name}: genuine/no-image/broken-image first batch`);
      await page.click('#news-refresh');
      await page.waitForFunction(() => document.querySelector('#zerohedge-feed .zh-feed-card .feed-card-title')?.getAttribute('title')?.includes(' 4'));
      const dynamicSecond = await inspect(page, 'dynamic-second', viewport.name);
      assert.deepEqual(dynamicSecond.zhCards.map(x => x.hasMedia), [true, false, false], `${viewport.name}: genuine/no-image/broken-image refreshed batch`);
      const screenshot = path.join(OUT, `${viewport.name}.png`);
      const section = page.locator('.compact-feed-card').first();
      await section.screenshot({ path: screenshot });
      observations.push({ viewport: viewport.name, expectedHeight: dynamicSecond.xCards[0].height, initial, dynamicFirst, dynamicSecond, screenshot });
      await context.close();
    }
  } finally {
    await browser.close();
    await new Promise(resolve => server.close(resolve));
  }
  console.log(JSON.stringify({ ok: true, budgets: { title: 110, excerpt: 140 }, observations }, null, 2));
})().catch(error => {
  server.close(() => {});
  console.error(error.stack || error.message);
  process.exit(1);
});
