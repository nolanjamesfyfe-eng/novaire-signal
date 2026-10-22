'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const http = require('node:http');
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require('/root/clawd/novaire-operations-system/node_modules/playwright');
const streak = require('../lib/study-streak');

const root = path.join(__dirname, '..');
const fixedNow = '2026-10-24T05:00:00.000Z';
const today = '2026-10-24';
let server, origin, browser, serverDates, postCount, failPost, authorized;
function send(res, status, body, type = 'application/json') { res.writeHead(status, { 'Content-Type': type, 'Cache-Control': 'no-store' }); res.end(type === 'application/json' ? JSON.stringify(body) : body); }
function contentType(file) { return file.endsWith('.js') ? 'text/javascript' : file.endsWith('.css') ? 'text/css' : file.endsWith('.svg') ? 'image/svg+xml' : 'text/html'; }
async function body(req) { let value = ''; for await (const chunk of req) value += chunk; return JSON.parse(value || '{}'); }
async function fixedContext(options = {}) {
  const { dates = null, denyStorage = false, ...browserOptions } = options;
  const context = await browser.newContext(browserOptions);
  await context.addInitScript(({ fixedNow, dates, denyStorage }) => {
    const NativeDate = Date;
    window.Date = class extends NativeDate {
      constructor(...args) { super(...(args.length ? args : [fixedNow])); }
      static now() { return new NativeDate(fixedNow).valueOf(); }
      static parse(value) { return NativeDate.parse(value); }
      static UTC(...args) { return NativeDate.UTC(...args); }
    };
    if (denyStorage) {
      Storage.prototype.getItem = function () { throw new DOMException('blocked', 'SecurityError'); };
      Storage.prototype.setItem = function () { throw new DOMException('blocked', 'SecurityError'); };
    } else if (dates) {
      localStorage.setItem('nv_anki_click_dates_v1', JSON.stringify(dates));
    }
  }, { fixedNow, dates, denyStorage: Boolean(denyStorage) });
  return context;
}

test.before(async () => {
  serverDates = []; postCount = 0; failPost = false; authorized = false;
  process.env.TMPDIR ||= path.join(root, '.playwright-tmp');
  fs.mkdirSync(process.env.TMPDIR, { recursive: true });
  server = http.createServer(async (req, res) => {
    const url = new URL(req.url, 'http://localhost');
    if (url.pathname === '/api/study-streak') {
      if (!authorized) return send(res, 401, { error: 'Private study sync is not connected.' });
      if (req.method === 'POST') {
        postCount += 1;
        if (failPost) return send(res, 503, { error: 'Isolated test outage.' });
        const data = await body(req);
        const incoming = Array.isArray(data.localDates) ? data.localDates : [];
        if (data.action === 'click') incoming.push(today);
        serverDates = [...new Set([...serverDates, ...incoming])].sort();
      }
      return send(res, 200, { ...streak.summarize({ startedAt: '2026-10-21', clickDates: serverDates }, today), clickDates: serverDates, storage: 'private-cross-device' });
    }
    if (url.pathname === '/api/study-auth') return send(res, 401, { error: 'Isolated auth disabled.' });
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
test.beforeEach(() => { serverDates = []; postCount = 0; failPost = false; authorized = false; });

test('new unauthorized browser counts locally, opens AnkiWeb, deduplicates and survives reload', async () => {
  const context = await fixedContext({ viewport: { width: 1280, height: 900 } });
  await context.route('https://ankiweb.net/**', route => route.fulfill({ status: 200, contentType: 'text/html', body: '<title>Isolated AnkiWeb navigation</title>' }));
  const page = await context.newPage();
  await page.goto(`${origin}/#daily-study`, { waitUntil: 'domcontentloaded' });
  assert.match(await page.locator('#anki-streak-status').textContent(), /3 days missed · restart today/);
  const [popup] = await Promise.all([context.waitForEvent('page'), page.locator('#anki-study-link').click()]);
  await popup.waitForLoadState('domcontentloaded').catch(() => {});
  assert.match(popup.url(), /^https:\/\/ankiweb\.net\/decks\//);
  await page.waitForFunction(() => document.querySelector('#anki-streak-status')?.textContent.includes('clicked today'));
  assert.equal(await page.locator('#anki-streak-status').getAttribute('data-tone'), 'calm');
  await page.locator('#anki-study-link').focus();
  await Promise.all([context.waitForEvent('page'), page.keyboard.press('Enter')]);
  assert.deepEqual(await page.evaluate(() => JSON.parse(localStorage.getItem('nv_anki_click_dates_v1'))), [today]);
  await page.reload({ waitUntil: 'domcontentloaded' });
  await page.waitForFunction(() => document.querySelector('#anki-streak-status')?.textContent.includes('clicked today'));
  assert.match(await page.locator('#anki-sync-status').textContent(), /Saved locally/);
  assert.deepEqual(serverDates, [], 'unauthorized browser must not mutate shared history');
  await context.close();
});

test('zero, one, two and three missed-day states use the requested tones', async () => {
  const scenarios = [
    { dates: ['2026-10-23'], text: '1 day streak · click today', tone: 'warn' },
    { dates: ['2026-10-22'], text: '1 day missed · restart today', tone: 'warn' },
    { dates: ['2026-10-21'], text: '2 days missed · restart today', tone: 'warn' },
    { dates: [], text: '3 days missed · restart today', tone: 'urgent' },
  ];
  for (const scenario of scenarios) {
    const context = await fixedContext({ viewport: { width: 1280, height: 900 }, dates: scenario.dates });
    const page = await context.newPage();
    await page.goto(`${origin}/#daily-study`, { waitUntil: 'domcontentloaded' });
    assert.equal(await page.locator('#anki-streak-status').textContent(), scenario.text);
    assert.equal(await page.locator('#anki-streak-status').getAttribute('data-tone'), scenario.tone);
    await context.close();
  }
});

test('failed network still records locally and keeps mobile navigation/geometry intact', async () => {
  authorized = true; failPost = true;
  const context = await fixedContext({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true });
  await context.route('https://ankiweb.net/**', route => route.fulfill({ status: 200, contentType: 'text/html', body: '<title>Anki</title>' }));
  const page = await context.newPage();
  await page.goto(`${origin}/#daily-study`, { waitUntil: 'domcontentloaded' });
  const [popup] = await Promise.all([context.waitForEvent('page'), page.locator('#anki-study-link').click()]);
  await popup.waitForLoadState('domcontentloaded').catch(() => {});
  assert.match(popup.url(), /^https:\/\/ankiweb\.net\/decks\//);
  await page.waitForFunction(() => document.querySelector('#anki-sync-status')?.textContent.includes('sync offline'));
  assert.deepEqual(await page.evaluate(() => JSON.parse(localStorage.getItem('nv_anki_click_dates_v1'))), [today]);
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth), true);
  await page.screenshot({ path: path.join(root, 'qa-artifacts', 'anki-click-streak-mobile.png'), fullPage: false });
  await context.close();
});

test('denied localStorage is honest, tracks for the tab, and expiry/network fallback remains safe', async () => {
  const context = await fixedContext({ viewport: { width: 1280, height: 900 }, denyStorage: true });
  await context.route('https://ankiweb.net/**', route => route.fulfill({ status: 200, body: 'Anki' }));
  const page = await context.newPage();
  await page.goto(`${origin}/#daily-study`, { waitUntil: 'domcontentloaded' });
  await Promise.all([context.waitForEvent('page'), page.locator('#anki-study-link').click()]);
  await page.waitForFunction(() => document.querySelector('#anki-streak-status')?.textContent.includes('clicked today'));
  assert.match(await page.locator('#anki-sync-status').textContent(), /This tab only/);
  await page.reload({ waitUntil: 'domcontentloaded' });
  assert.equal(await page.locator('#anki-streak-status').textContent(), '3 days missed · restart today');
  await context.close();
});

test('authorized devices merge canonical history; another authorized device reads it; unauthorized browser cannot', async () => {
  authorized = true; serverDates = ['2026-10-21'];
  const first = await fixedContext({ viewport: { width: 1280, height: 900 }, dates: ['2026-10-22'] });
  const page = await first.newPage();
  await page.goto(`${origin}/#daily-study`, { waitUntil: 'domcontentloaded' });
  await page.waitForFunction(() => document.querySelector('#anki-sync-status')?.textContent.includes('synced'));
  assert.equal(await page.locator('#anki-sync-control').isVisible(), false, 'connected devices should not show the PIN control');
  assert.deepEqual(serverDates, ['2026-10-21', '2026-10-22']);
  assert.equal(postCount, 1, 'queued local history should merge once');
  await page.reload({ waitUntil: 'domcontentloaded' });
  await page.waitForFunction(() => document.querySelector('#anki-sync-status')?.textContent.includes('synced'));
  assert.equal(postCount, 1, 'reload must not rewrite already merged history');
  await first.close();

  const second = await fixedContext({ viewport: { width: 390, height: 844 } });
  const secondPage = await second.newPage();
  await secondPage.goto(`${origin}/#daily-study`, { waitUntil: 'domcontentloaded' });
  await secondPage.waitForFunction(() => document.querySelector('#anki-sync-status')?.textContent.includes('synced'));
  assert.deepEqual(await secondPage.evaluate(() => JSON.parse(localStorage.getItem('nv_anki_click_dates_v1'))), serverDates);
  authorized = false;
  await secondPage.reload({ waitUntil: 'domcontentloaded' });
  await secondPage.waitForFunction(() => document.querySelector('#anki-sync-status')?.textContent.includes('Saved locally'));
  assert.equal(await secondPage.locator('#anki-sync-control').isVisible(), true, 'expired auth should reveal only the tiny reconnect control');
  await second.close();

  const stranger = await fixedContext({ viewport: { width: 390, height: 844 } });
  const strangerPage = await stranger.newPage();
  await strangerPage.goto(`${origin}/#daily-study`, { waitUntil: 'domcontentloaded' });
  assert.equal(await strangerPage.locator('#anki-streak-status').textContent(), '3 days missed · restart today');
  assert.deepEqual(await strangerPage.evaluate(() => JSON.parse(localStorage.getItem('nv_anki_click_dates_v1') || '[]')), []);
  await stranger.close();
});

test('compact row is rendered on desktop/mobile and unrelated accordion state survives navigation', async () => {
  for (const viewport of [{ name: 'desktop', width: 1280, height: 900, maxHeight: 70 }, { name: 'mobile', width: 390, height: 844, maxHeight: 76 }]) {
    const context = await fixedContext({ viewport, isMobile: viewport.name === 'mobile', hasTouch: viewport.name === 'mobile' });
    const page = await context.newPage();
    await page.goto(`${origin}/#daily-study`, { waitUntil: 'domcontentloaded' });
    const card = page.locator('#daily-study'), box = await card.boundingBox();
    assert.ok(box && box.height <= viewport.maxHeight, `${viewport.name} row is ${box?.height}px tall`);
    const other = page.locator('#world-tour-card');
    if (await other.getAttribute('open') !== null) await other.locator(':scope > summary').click();
    await page.reload({ waitUntil: 'domcontentloaded' });
    assert.equal(await page.locator('#world-tour-card').getAttribute('open'), null, `${viewport.name}: unrelated accordion state changed`);
    await card.evaluate(node => node.scrollIntoView({ block: 'center' }));
    await page.screenshot({ path: path.join(root, 'qa-artifacts', `anki-click-streak-${viewport.name}.png`), fullPage: false });
    await context.close();
  }
});
