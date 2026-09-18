#!/usr/bin/env node
'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const { chromium, request } = require('/root/clawd/novaire-operations-system/node_modules/playwright');

const BASE = (process.env.NOVAIRE_SIGNAL_BASE_URL || 'https://novairesignal.com').replace(/\/$/, '');
const RUNS = Number(process.env.DAILY_VERIFY_RUNS || 3);
const FAILURE_DIR = process.env.DAILY_VERIFY_FAILURE_DIR || 'qa-artifacts/daily-convergence-failures';
function secret(name) {
  if (process.env[name]) return process.env[name];
  const file = process.env.NOVAIRE_SIGNAL_SECRETS || '/root/clawd/.secrets';
  if (!fs.existsSync(file)) return '';
  const row = fs.readFileSync(file, 'utf8').split(/\r?\n/).find(line => line.startsWith(`${name}=`));
  return row ? row.slice(name.length + 1).trim() : '';
}
function safeStamp() { return new Date().toISOString().replace(/[:.]/g, '-'); }
async function recordFailure({ page, response, label, requestedUrl, value, error }) {
  fs.mkdirSync(FAILURE_DIR, { recursive: true });
  const stem = `${safeStamp()}-${label.replace(/[^a-z0-9-]+/gi, '-')}`;
  const html = await page.content().catch(() => '<!-- page.content() unavailable -->');
  const htmlPath = `${FAILURE_DIR}/${stem}.html`;
  const jsonPath = `${FAILURE_DIR}/${stem}.json`;
  fs.writeFileSync(htmlPath, html);
  const headers = response ? response.headers() : {};
  fs.writeFileSync(jsonPath, JSON.stringify({
    label,
    requestedUrl,
    finalUrl: page.url(),
    status: response?.status() ?? null,
    headers: {
      'content-type': headers['content-type'] || null,
      'cache-control': headers['cache-control'] || null,
      'location': headers.location || null,
      'server': headers.server || null,
      'x-vercel-id': headers['x-vercel-id'] || null,
    },
    value: value || null,
    error: error?.message || String(error),
    htmlPath,
    capturedAt: new Date().toISOString(),
  }, null, 2) + '\n');
  console.error(`Daily convergence failure recorded: ${jsonPath} ${htmlPath}`);
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
          const requestedUrl = `${BASE}/portfolio/daily/${suffix}`;
          let response;
          let value;
          const label = `${viewport.name}/${mode}/${run}`;
          try {
            response = await page.goto(requestedUrl, { waitUntil: 'networkidle', timeout: 60000 });
            assert.ok(response, `${label} missing navigation response`);
            assert.equal(response.status(), 200, `${label} status`);
            assert.ok(!page.url().includes('portfolio-lock'), `${label} auth gate`);
            value = await page.evaluate(() => {
            const row = document.querySelector('.daily-header .signal-brand-row');
            const rect = row?.getBoundingClientRect();
            const title = document.querySelector('.daily-title');
            return {
              title: title?.textContent.trim(),
              legacyHeaderH1: Boolean(document.querySelector('.daily-header > h1:not(.daily-title)')),
              fontSize: row && getComputedStyle(row).fontSize,
              centerDelta: rect && Math.abs(rect.left + rect.width / 2 - innerWidth / 2),
              geopolitical: document.body.textContent.includes('Geopolitical pressure'),
              storyCount: document.querySelectorAll('.story').length,
              accountCards: document.querySelectorAll('.accounts .account').length,
              movers: document.querySelectorAll('.movers .mover').length,
            };
          });
            assert.equal(value.title, 'The Daily.', `${label} title`);
            assert.equal(value.legacyHeaderH1, false, `${label} legacy h1`);
            assert.equal(value.fontSize, viewport.name === 'desktop' ? '31.68px' : '28.8px', `${label} font`);
            assert.ok(value.centerDelta < 25, `${label} centered`);
            assert.equal(value.geopolitical, false, `${label} stale geopolitical story`);
            assert.equal(value.storyCount, 0, `${label} stale stories`);
            assert.equal(value.accountCards, 3, `${label} account cards preserved`);
            observations.push({ viewport: viewport.name, mode, run, url: page.url(), deployment: response.headers()['x-vercel-id'] || null, ...value });
          } catch (error) {
            await recordFailure({ page, response, label, requestedUrl, value, error });
            throw error;
          } finally {
            await page.close();
          }
        }
      }
      await context.close();
    }
  } finally {
    await browser.close();
  }
  console.log(JSON.stringify({ ok: true, base: BASE, runs: RUNS, observations }, null, 2));
})().catch(error => { console.error(error.stack || error.message); process.exit(1); });
