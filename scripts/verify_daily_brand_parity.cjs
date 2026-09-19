#!/usr/bin/env node
'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { chromium, request } = require('/root/clawd/novaire-operations-system/node_modules/playwright');

const BASE = (process.env.NOVAIRE_SIGNAL_BASE_URL || 'https://novairesignal.com').replace(/\/$/, '');
const OUT = process.env.NOVAIRE_SIGNAL_PARITY_OUT || path.resolve(__dirname, '..', 'qa-artifacts', 'daily-brand-parity');
function secret(name) {
  if (process.env[name]) return process.env[name];
  const file = process.env.NOVAIRE_SIGNAL_SECRETS || '/root/clawd/.secrets';
  if (!fs.existsSync(file)) return '';
  const row = fs.readFileSync(file, 'utf8').split(/\r?\n/).find(line => line.startsWith(`${name}=`));
  return row ? row.slice(name.length + 1).trim() : '';
}
function close(actual, expected, tolerance, label) {
  assert.ok(Math.abs(actual - expected) <= tolerance, `${label}: ${actual} != ${expected} (±${tolerance})`);
}
async function platformFonts(cdp, selector) {
  const document = await cdp.send('DOM.getDocument', { depth: 0 });
  const node = await cdp.send('DOM.querySelector', { nodeId: document.root.nodeId, selector });
  assert.ok(node.nodeId, `missing CDP node ${selector}`);
  return (await cdp.send('CSS.getPlatformFontsForNode', { nodeId: node.nodeId })).fonts;
}
async function measure(page, cdp, selector) {
  await page.evaluate(async () => { await document.fonts.ready; });
  const result = await page.locator(selector).evaluate(el => {
    const inspect = childSelector => {
      const node = el.querySelector(childSelector);
      const style = getComputedStyle(node);
      const rect = node.getBoundingClientRect();
      return { style: { fontFamily: style.fontFamily, fontSize: style.fontSize, fontWeight: style.fontWeight, fontStyle: style.fontStyle, letterSpacing: style.letterSpacing, lineHeight: style.lineHeight, textTransform: style.textTransform }, rect: { width: rect.width, height: rect.height } };
    };
    const style = getComputedStyle(el);
    const rect = el.getBoundingClientRect();
    return {
      style: { fontFamily: style.fontFamily, fontSize: style.fontSize, fontWeight: style.fontWeight, fontStyle: style.fontStyle, letterSpacing: style.letterSpacing, lineHeight: style.lineHeight, textTransform: style.textTransform, gap: style.gap },
      rect: { width: rect.width, height: rect.height },
      wordmark: inspect('.signal-wordmark'), signal: inspect('.signal-wordmark > span'),
      globe: inspect('.signal-map'), globeSvg: inspect('.signal-map-icon'),
      bolt: inspect('.signal-bolt'), boltSvg: inspect('.signal-bolt-icon'),
    };
  });
  result.platformFonts = await platformFonts(cdp, `${selector} .signal-wordmark`);
  return result;
}
function assertParity(home, daily, viewport) {
  assert.deepEqual(daily.style, home.style, `${viewport}: row computed typography`);
  assert.deepEqual(daily.wordmark.style, home.wordmark.style, `${viewport}: wordmark computed typography`);
  assert.deepEqual(daily.signal.style, home.signal.style, `${viewport}: Signal computed typography`);
  for (const part of ['rect', 'wordmark', 'globe', 'globeSvg', 'bolt', 'boltSvg']) {
    const a = part === 'rect' ? daily.rect : daily[part].rect;
    const b = part === 'rect' ? home.rect : home[part].rect;
    close(a.width, b.width, 0.2, `${viewport}: ${part} width`);
    close(a.height, b.height, 0.2, `${viewport}: ${part} height`);
  }
  for (const [side, measured] of [['homepage', home], ['daily', daily]]) {
    assert.ok(measured.platformFonts.some(font => font.familyName === 'Cormorant Garamond Light' && font.postScriptName === 'CormorantGaramond-Light' && font.isCustomFont), `${viewport}: ${side} must render the loaded Cormorant Garamond Light webfont`);
  }
}
(async () => {
  const pin = secret('NOS_ACCESS_PIN') || secret('NOVAIRE_SIGNAL_PORTFOLIO_PASSWORD');
  assert.ok(pin, 'portfolio PIN unavailable');
  fs.mkdirSync(OUT, { recursive: true });
  const api = await request.newContext({ baseURL: BASE });
  const auth = await api.post('/api/portfolio-auth', { data: { pin } });
  assert.equal(auth.status(), 200, 'portfolio authentication failed');
  const cookie = (auth.headers()['set-cookie'] || '').split(';', 1)[0];
  assert.ok(cookie, 'portfolio auth cookie missing');
  await api.dispose();
  const browser = await chromium.launch({ headless: true, executablePath: process.env.CHROMIUM_PATH || '/snap/bin/chromium', args: ['--no-sandbox'] });
  const observations = [];
  try {
    for (const viewport of [{ name: 'desktop', width: 1280, height: 900 }, { name: 'mobile', width: 390, height: 844 }]) {
      const captures = [];
      const measured = {};
      for (const [name, route, selector] of [['homepage', '/', '.header-brand .signal-brand-row'], ['daily', '/portfolio/daily/', '.daily-header .signal-brand-row']]) {
        const context = await browser.newContext({ viewport, extraHTTPHeaders: name === 'daily' ? { Cookie: cookie } : {} });
        const page = await context.newPage();
        const response = await page.goto(`${BASE}${route}?brand_parity=${Date.now()}`, { waitUntil: 'networkidle', timeout: 60000 });
        assert.equal(response.status(), 200, `${viewport.name} ${name}: HTTP status`);
        const cdp = await context.newCDPSession(page); await cdp.send('DOM.enable'); await cdp.send('CSS.enable');
        measured[name] = await measure(page, cdp, selector);
        captures.push((await page.screenshot({ type: 'png', fullPage: false })).toString('base64'));
        await context.close();
      }
      assertParity(measured.homepage, measured.daily, viewport.name);
      const compare = await browser.newPage({ viewport: { width: viewport.width * 2, height: viewport.height } });
      await compare.setContent(`<style>*{box-sizing:border-box}html,body{margin:0;background:#000}body{display:flex}img{display:block;width:${viewport.width}px;height:${viewport.height}px;object-fit:cover;object-position:top}</style><img alt="homepage" src="data:image/png;base64,${captures[0]}"><img alt="daily" src="data:image/png;base64,${captures[1]}">`);
      const screenshot = path.join(OUT, `${viewport.name}-homepage-vs-daily.png`);
      await compare.screenshot({ path: screenshot }); await compare.close();
      observations.push({ viewport: viewport.name, homepage: measured.homepage, daily: measured.daily, screenshot });
    }
  } finally { await browser.close(); }
  console.log(JSON.stringify({ ok: true, base: BASE, authenticated: true, secretPrinted: false, observations }, null, 2));
})().catch(error => { console.error(error.stack || error.message); process.exit(1); });
