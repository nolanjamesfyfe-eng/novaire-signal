'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const http = require('node:http');
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require('/root/clawd/novaire-operations-system/node_modules/playwright');
const streak = require('../lib/study-streak');

const root = path.join(__dirname, '..');
let server, origin, browser, clickDates, postCount, failPost;
const today = '2026-10-21';
function send(res, status, body, type = 'application/json') { res.writeHead(status, { 'Content-Type': type, 'Cache-Control': 'no-store' }); res.end(type === 'application/json' ? JSON.stringify(body) : body); }
function contentType(file) { return file.endsWith('.js') ? 'text/javascript' : file.endsWith('.css') ? 'text/css' : file.endsWith('.svg') ? 'image/svg+xml' : 'text/html'; }

test.before(async () => {
  clickDates = []; postCount = 0; failPost = false;
  process.env.TMPDIR = path.join(root, 'tests', '.pw-study-tmp');
  fs.mkdirSync(process.env.TMPDIR, { recursive: true });
  server = http.createServer((req, res) => {
    const url = new URL(req.url, 'http://localhost');
    if (url.pathname === '/api/study-streak') {
      if (req.method === 'POST') {
        postCount += 1;
        if (failPost) return send(res, 503, { error: 'Isolated test outage.' });
        if (!clickDates.includes(today)) clickDates.push(today);
      }
      return send(res, 200, { ...streak.summarize({ startedAt: today, clickDates }, today), storage: 'private-cross-device', deduplicated: clickDates.includes(today) && postCount > 1 });
    }
    if (url.pathname.startsWith('/api/')) return send(res, 503, { error: 'not part of isolated test' });
    const relative = url.pathname === '/' ? 'index.html' : url.pathname.replace(/^\//, '');
    const file = path.resolve(root, relative);
    if (!file.startsWith(root) || !fs.existsSync(file) || fs.statSync(file).isDirectory()) return send(res, 404, 'not found', 'text/plain');
    send(res, 200, fs.readFileSync(file), contentType(file));
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  origin = `http://127.0.0.1:${server.address().port}`;
  browser = await chromium.launch({ headless: true, executablePath: '/snap/bin/chromium', args: ['--no-sandbox'] });
});
test.after(async () => { await browser?.close(); await new Promise(resolve => server?.close(resolve)); });

test('ordinary and keyboard anchor activation navigate while deduplicating the click day', async () => {
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  await context.route('https://ankiweb.net/**', route => route.fulfill({ status: 200, contentType: 'text/html', body: '<title>Isolated AnkiWeb navigation</title>' }));
  const page = await context.newPage();
  const errors = []; page.on('pageerror', error => errors.push(error.message));
  await page.goto(`${origin}/#daily-study`, { waitUntil: 'domcontentloaded' });
  await page.locator('#anki-today-status').waitFor({ state: 'visible' });
  assert.equal(postCount, 0, 'page load must not count as a click');
  const [popup] = await Promise.all([context.waitForEvent('page'), page.locator('#anki-study-link').click()]);
  await popup.waitForLoadState('domcontentloaded').catch(() => {});
  assert.match(popup.url(), /^https:\/\/ankiweb\.net\/decks\//);
  await page.locator('#anki-today-status').waitFor({ state: 'visible' });
  await page.waitForFunction(() => document.querySelector('#anki-today-status')?.textContent.includes('clicked'));
  await page.locator('#anki-study-link').focus();
  const [keyboardPopup] = await Promise.all([context.waitForEvent('page'), page.keyboard.press('Enter')]);
  await keyboardPopup.waitForLoadState('domcontentloaded').catch(() => {});
  await page.waitForFunction(() => document.querySelector('#anki-sync-status')?.textContent.includes('already recorded'));
  assert.equal(postCount, 2);
  assert.deepEqual(clickDates, [today]);
  await page.reload({ waitUntil: 'domcontentloaded' });
  await page.waitForFunction(() => document.querySelector('#anki-today-status')?.textContent.includes('clicked'));
  const card = page.locator('#daily-study');
  await card.locator(':scope > summary').click();
  assert.equal(await card.getAttribute('open'), null);
  await page.waitForFunction(() => localStorage.getItem('nv_accordion_state_daily-study') === 'closed');
  await page.reload({ waitUntil: 'domcontentloaded' });
  assert.equal(await page.locator('#daily-study').getAttribute('open'), null, 'accordion preference survives refresh');
  await page.locator('#daily-study > summary').click();
  await page.screenshot({ path: path.join(root, 'qa-artifacts', 'daily-study-option-e-desktop.png'), fullPage: false });
  assert.deepEqual(errors, []);
  await context.close();
});

test('request failure is visible and does not prevent Anki navigation on mobile', async () => {
  failPost = true;
  const context = await browser.newContext({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true });
  await context.route('https://ankiweb.net/**', route => route.fulfill({ status: 200, contentType: 'text/html', body: '<title>Isolated AnkiWeb navigation</title>' }));
  const page = await context.newPage();
  await page.goto(`${origin}/#daily-study`, { waitUntil: 'domcontentloaded' });
  const [popup] = await Promise.all([context.waitForEvent('page'), page.locator('#anki-study-link').click()]);
  await popup.waitForLoadState('domcontentloaded').catch(() => {});
  assert.match(popup.url(), /^https:\/\/ankiweb\.net\/decks\//);
  await page.waitForFunction(() => document.querySelector('#anki-sync-status')?.textContent.includes('click not recorded'));
  assert.match(await page.locator('#anki-sync-status').textContent(), /Isolated test outage/);
  await page.locator('#daily-study').evaluate(node => node.scrollIntoView({ block: 'start' }));
  await page.waitForTimeout(100);
  await page.screenshot({ path: path.join(root, 'qa-artifacts', 'daily-study-option-e-mobile.png'), fullPage: false });
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth), true);
  await context.close();
  failPost = false;
});

test('collapsed reminder stays slim on desktop and mobile and preserves exact accordion state', async () => {
  for (const viewport of [{ name: 'desktop', width: 1440, height: 900, maxHeight: 47 }, { name: 'mobile', width: 390, height: 844, maxHeight: 41 }]) {
    const context = await browser.newContext({ viewport: { width: viewport.width, height: viewport.height }, isMobile: viewport.name === 'mobile', hasTouch: viewport.name === 'mobile' });
    const page = await context.newPage();
    await page.goto(`${origin}/#daily-study`, { waitUntil: 'domcontentloaded' });
    const card = page.locator('#daily-study');
    if (await card.getAttribute('open') !== null) await card.locator(':scope > summary').click();
    await page.waitForFunction(() => localStorage.getItem('nv_accordion_state_daily-study') === 'closed');
    const before = await card.boundingBox();
    assert.ok(before && before.height <= viewport.maxHeight, `${viewport.name} collapsed height ${before?.height}px exceeds ${viewport.maxHeight}px`);
    await page.reload({ waitUntil: 'domcontentloaded' });
    assert.equal(await card.getAttribute('open'), null, `${viewport.name} collapsed state changed after reload`);
    const after = await card.boundingBox();
    assert.ok(after && Math.abs(after.height - before.height) < 0.1, `${viewport.name} collapsed geometry changed after reload`);
    await card.locator(':scope > summary').click();
    await card.locator(':scope > summary').click();
    const focusStyle = await card.locator(':scope > summary').evaluate(node => ({ focusVisible: node.matches(':focus-visible'), outlineStyle: getComputedStyle(node).outlineStyle }));
    assert.equal(focusStyle.focusVisible, false, `${viewport.name} pointer focus incorrectly uses the keyboard ring`);
    assert.equal(focusStyle.outlineStyle, 'none', `${viewport.name} pointer focus should not draw an inner frame`);
    await page.keyboard.press('Tab');
    await page.keyboard.press('Shift+Tab');
    const keyboardFocus = await card.locator(':scope > summary').evaluate(node => ({ matches: node.matches(':focus-visible'), outlineWidth: getComputedStyle(node).outlineWidth }));
    assert.equal(keyboardFocus.matches, true, `${viewport.name} summary is not keyboard focus-visible`);
    assert.ok(parseFloat(keyboardFocus.outlineWidth) >= 1.7, `${viewport.name} keyboard focus ring is missing`);
    await context.close();
  }
});
