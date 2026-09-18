#!/usr/bin/env node
'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const { chromium, request } = require('/root/clawd/novaire-operations-system/node_modules/playwright');

const BASE = (process.env.NOVAIRE_SIGNAL_BASE_URL || 'https://novairesignal.com').replace(/\/$/, '');
const EXACT_URL = `${BASE}/portfolio/daily/`;
function secret(name) {
  if (process.env[name]) return process.env[name];
  const file = process.env.NOVAIRE_SIGNAL_SECRETS || '/root/clawd/.secrets';
  if (!fs.existsSync(file)) return '';
  const row = fs.readFileSync(file, 'utf8').split(/\r?\n/).find(line => line.startsWith(`${name}=`));
  return row ? row.slice(name.length + 1).trim() : '';
}

(async () => {
  const pin = secret('NOS_ACCESS_PIN') || secret('NOVAIRE_SIGNAL_PORTFOLIO_PASSWORD');
  assert.ok(pin, 'portfolio PIN is unavailable in the configured secret file');
  const api = await request.newContext({ baseURL: BASE });
  const auth = await api.post('/api/portfolio-auth', { data: { pin } });
  assert.equal(auth.status(), 200, 'portfolio authentication failed');
  const cookie = (auth.headers()['set-cookie'] || '').split(';', 1)[0];
  assert.ok(cookie, 'portfolio authentication did not set a cookie');
  await api.dispose();

  const browser = await chromium.launch({
    headless: true,
    executablePath: process.env.CHROMIUM_PATH || '/snap/bin/chromium',
    args: ['--no-sandbox'],
  });
  const observations = [];
  try {
    for (const viewport of [{ name: 'desktop', width: 1280, height: 900 }, { name: 'mobile', width: 390, height: 844 }]) {
      const context = await browser.newContext({ viewport, extraHTTPHeaders: { Cookie: cookie } });
      const page = await context.newPage();
      const response = await page.goto(`${EXACT_URL}?verify_daily=${Date.now()}-${viewport.name}`, { waitUntil: 'networkidle', timeout: 60000 });
      assert.equal(response.status(), 200, `${viewport.name}: HTTP status`);
      assert.ok(!page.url().includes('portfolio-lock'), `${viewport.name}: auth gate remained`);
      const result = await page.evaluate(() => {
        const cards = [...document.querySelectorAll('.accounts .account')];
        cards.forEach(card => card.open = true);
        const text = document.body.innerText;
        cards.forEach(card => card.open = false);
        const compactHeights = cards.map(card => card.getBoundingClientRect().height);
        const style = document.createElement('style');
        style.id = 'prior-daily-card-baseline';
        style.textContent = `
          summary{gap:12px!important;min-height:45px!important;padding:13px 15px!important}
          .account-detail{padding:13px 15px 15px!important}
          .source{padding-bottom:11px!important}
          .position{gap:16px!important}
          .quote-grid,.impact-grid{gap:7px!important;margin-top:11px!important}
          .quote-grid>div,.impact-grid>div{padding:10px 11px!important}
          .periods{margin-top:11px!important}
          @media(max-width:430px){summary{padding:13px 15px!important}.account-detail{padding:13px 15px 15px!important}.position{gap:16px!important}.position-move{padding-left:14px!important}}
        `;
        document.head.appendChild(style);
        const baselineHeights = cards.map(card => card.getBoundingClientRect().height);
        const reductions = compactHeights.map((height, index) => 1 - height / baselineHeights[index]);
        return {
          title: document.querySelector('.daily-title')?.textContent.trim(),
          brandBeforeTitle: Boolean(document.querySelector('.daily-header > .signal-brand-row + .daily-title')),
          storyCount: document.querySelectorAll('.story').length,
          accountCards: cards.length,
          accountLabels: cards.map(card => card.querySelector('.account-kicker')?.textContent.trim()),
          hasRetiredNews: /Geopolitical pressure|Thailand signal|Market signal/i.test(text),
          hasMisleadingIntradayLabel: /INTRADAY SWING/i.test(text),
          hasTruthfulRangeLabel: /POSITION SESSION RANGE/i.test(text),
          hasCompletedSessionDate: /Completed session · \d{4}-\d{2}-\d{2}/.test(text),
          hasInvalidNumber: /\b(?:NaN|undefined|null)\b/.test(text),
          compactHeights,
          baselineHeights,
          reductions,
        };
      });
      assert.equal(result.title, 'The Daily.', `${viewport.name}: title`);
      assert.equal(result.brandBeforeTitle, true, `${viewport.name}: canonical brand must precede title`);
      assert.equal(result.storyCount, 0, `${viewport.name}: news/story cards`);
      assert.equal(result.hasRetiredNews, false, `${viewport.name}: retired news copy`);
      assert.deepEqual(result.accountLabels, ['WS TFSA', 'RRSP', 'Novairecito'], `${viewport.name}: account cards`);
      assert.equal(result.hasMisleadingIntradayLabel, false, `${viewport.name}: misleading metric label`);
      assert.equal(result.hasTruthfulRangeLabel, true, `${viewport.name}: truthful position-range label`);
      assert.equal(result.hasCompletedSessionDate, true, `${viewport.name}: completed-session disclosure`);
      assert.equal(result.hasInvalidNumber, false, `${viewport.name}: invalid numeric output`);
      result.reductions.forEach((value, index) => assert.ok(value >= 0.25, `${viewport.name}: collapsed card ${index + 1} is only ${(value * 100).toFixed(1)}% shorter than baseline`));
      observations.push({ viewport: viewport.name, url: EXACT_URL, deployment: response.headers()['x-vercel-id'] || null, ...result });
      await context.close();
    }
  } finally {
    await browser.close();
  }
  console.log(JSON.stringify({ ok: true, authenticated: true, secretPrinted: false, observations }, null, 2));
})().catch(error => { console.error(error.stack || error.message); process.exit(1); });
