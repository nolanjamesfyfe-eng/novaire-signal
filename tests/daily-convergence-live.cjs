#!/usr/bin/env node
'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const { chromium, request } = require('/root/clawd/novaire-operations-system/node_modules/playwright');

const BASE = (process.env.NOVAIRE_SIGNAL_BASE_URL || 'https://novairesignal.com').replace(/\/$/, '');
const RUNS = Number(process.env.DAILY_VERIFY_RUNS || 3);
function secret(name) {
  if (process.env[name]) return process.env[name];
  const file = process.env.NOVAIRE_SIGNAL_SECRETS || '/root/clawd/.secrets';
  if (!fs.existsSync(file)) return '';
  const row = fs.readFileSync(file, 'utf8').split(/\r?\n/).find(line => line.startsWith(`${name}=`));
  return row ? row.slice(name.length + 1).trim() : '';
}

(async () => {
  const pin = secret('NOS_ACCESS_PIN') || secret('NOVAIRE_SIGNAL_PORTFOLIO_PASSWORD');
  assert.ok(pin, 'NOS_ACCESS_PIN or NOVAIRE_SIGNAL_PORTFOLIO_PASSWORD is required');
  const api = await request.newContext({ baseURL: BASE });
  const auth = await api.post('/api/portfolio-auth', { data: { pin } });
  assert.equal(auth.status(), 200, 'portfolio authentication failed');
  const setCookie = auth.headers()['set-cookie'] || '';
  assert.ok(setCookie, 'portfolio authentication did not set a cookie');
  const cookie = setCookie.split(';', 1)[0];
  await api.dispose();

  const browser = await chromium.launch({ headless: true, executablePath: process.env.CHROMIUM_PATH || '/snap/bin/chromium', args: ['--no-sandbox'] });
  const observations = [];
  try {
    for (const viewport of [{ name: 'desktop', width: 1280, height: 900 }, { name: 'mobile', width: 390, height: 844 }]) {
      const context = await browser.newContext({ viewport, extraHTTPHeaders: { Cookie: cookie } });
      for (let run = 1; run <= RUNS; run++) {
        for (const mode of ['ordinary', 'cache-busted']) {
          const page = await context.newPage();
          const suffix = mode === 'cache-busted' ? `?daily_verify=${Date.now()}-${viewport.name}-${run}` : '';
          const response = await page.goto(`${BASE}/portfolio/daily/${suffix}`, { waitUntil: 'networkidle', timeout: 60000 });
          assert.equal(response.status(), 200, `${viewport.name}/${mode}/${run} status`);
          assert.ok(!page.url().includes('portfolio-lock'), `${viewport.name}/${mode}/${run} auth gate`);
          const value = await page.evaluate(() => {
            const row = document.querySelector('.daily-header .signal-brand-row');
            const rect = row?.getBoundingClientRect();
            const title = document.querySelector('.daily-title');
            return {
              title: title?.textContent.trim(),
              inlineHeaderH1: Boolean(document.querySelector('.daily-header h1')),
              fontSize: row && getComputedStyle(row).fontSize,
              centerDelta: rect && Math.abs(rect.left + rect.width / 2 - innerWidth / 2),
              geopolitical: document.body.textContent.includes('Geopolitical pressure'),
              storyCount: document.querySelectorAll('.story').length,
              accountCards: document.querySelectorAll('.accounts .account').length,
              movers: document.querySelectorAll('.movers .mover').length,
            };
          });
          assert.equal(value.title, 'The Daily.', `${viewport.name}/${mode}/${run} title`);
          assert.equal(value.inlineHeaderH1, false, `${viewport.name}/${mode}/${run} stale inline h1`);
          assert.equal(value.fontSize, viewport.name === 'desktop' ? '31.68px' : '28.8px', `${viewport.name}/${mode}/${run} font`);
          assert.ok(value.centerDelta < 25, `${viewport.name}/${mode}/${run} centered`);
          assert.equal(value.geopolitical, false, `${viewport.name}/${mode}/${run} stale geopolitical story`);
          assert.equal(value.storyCount, 0, `${viewport.name}/${mode}/${run} stale stories`);
          assert.ok(value.accountCards > 0, `${viewport.name}/${mode}/${run} account cards preserved`);
          observations.push({ viewport: viewport.name, mode, run, deployment: response.headers()['x-vercel-id'] || null, ...value });
          await page.close();
        }
      }
      await context.close();
    }
  } finally {
    await browser.close();
  }
  console.log(JSON.stringify({ ok: true, base: BASE, runs: RUNS, observations }, null, 2));
})().catch(error => { console.error(error.stack || error.message); process.exit(1); });
