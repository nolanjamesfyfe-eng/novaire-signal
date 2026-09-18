#!/usr/bin/env node
'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const { chromium, request } = require('/root/clawd/novaire-operations-system/node_modules/playwright');

const BASE = (process.env.NOVAIRE_SIGNAL_BASE_URL || 'https://novairesignal.com').replace(/\/$/, '');
function secret(name) {
  if (process.env[name]) return process.env[name];
  const file = process.env.NOVAIRE_SIGNAL_SECRETS || '/root/clawd/.secrets';
  if (!fs.existsSync(file)) return '';
  const line = fs.readFileSync(file, 'utf8').split(/\r?\n/).find(row => row.startsWith(`${name}=`));
  return line ? line.slice(name.length + 1).trim() : '';
}

(async () => {
  const pin = secret('NOVAIRE_SIGNAL_PORTFOLIO_PASSWORD');
  assert.ok(pin, 'NOVAIRE_SIGNAL_PORTFOLIO_PASSWORD is required in the environment or secrets file');
  const api = await request.newContext({ baseURL: BASE });
  const response = await api.post('/api/portfolio-auth', { data: { pin } });
  assert.equal(response.status(), 200, 'portfolio authentication failed');
  const cookieHeader = response.headers()['set-cookie'] || '';
  assert.ok(cookieHeader, 'portfolio authentication did not set a cookie');
  const cookie = cookieHeader.split(';', 1)[0];
  await api.dispose();

  const browser = await chromium.launch({ headless: true, executablePath: process.env.CHROMIUM_PATH || '/snap/bin/chromium', args: ['--no-sandbox'] });
  const routes = ['/', '/flaneur', '/portfolio/', '/portfolio/daily/'];
  const report = {};
  try {
    for (const viewport of [{ name: 'desktop', width: 1280, height: 900 }, { name: 'mobile', width: 390, height: 844 }]) {
      const context = await browser.newContext({ viewport, extraHTTPHeaders: { Cookie: cookie } });
      report[viewport.name] = {};
      let baseline;
      for (const route of routes) {
        const page = await context.newPage();
        const url = `${BASE}${route}?brand_verify=${Date.now()}`;
        const nav = await page.goto(url, { waitUntil: 'networkidle', timeout: 60000 });
        assert.equal(nav.status(), 200, `${route} returned ${nav.status()}`);
        assert.ok(!page.url().includes('portfolio-lock'), `${route} unexpectedly showed auth gate`);
        await page.evaluate(() => document.fonts.ready);
        const value = await page.locator('.signal-brand-row').first().evaluate(row => {
          const wordmark = row.querySelector('.signal-wordmark');
          const signal = wordmark.querySelector(':scope > span');
          const globe = row.querySelector('.signal-map-icon');
          const bolt = row.querySelector('.signal-bolt-icon');
          const rect = row.getBoundingClientRect();
          return {
            text: wordmark.textContent.replace(/\s+/g, ' ').trim(),
            fontSize: getComputedStyle(row).fontSize,
            fontFamily: getComputedStyle(wordmark).fontFamily,
            gap: getComputedStyle(row).gap,
            centerDelta: Math.abs(rect.left + rect.width / 2 - innerWidth / 2),
            geometry: { x: rect.x, y: rect.y, width: rect.width, height: rect.height },
            novaireColor: getComputedStyle(wordmark).color,
            novaireStyle: getComputedStyle(wordmark).fontStyle,
            signalColor: getComputedStyle(signal).color,
            signalStyle: getComputedStyle(signal).fontStyle,
            globeAnimation: getComputedStyle(globe).animationName,
            globeDelay: getComputedStyle(globe).animationDelay,
            boltAnimation: getComputedStyle(bolt).animationName,
            boltDelay: getComputedStyle(bolt).animationDelay,
            links: [row.querySelector('.signal-map').getAttribute('href'), wordmark.getAttribute('href'), row.querySelector('.signal-bolt').getAttribute('href')],
          };
        });
        assert.equal(value.text.toLowerCase(), 'novaire signal');
        assert.equal(value.fontSize, viewport.name === 'desktop' ? '31.68px' : '28.8px', `${route} font size`);
        assert.equal(value.gap, '12px', `${route} gap`);
        assert.ok(value.centerDelta < 25, `${route} centered (${value.centerDelta}px delta)`);
        assert.equal(value.novaireColor, 'rgb(240, 238, 248)', `${route} NOVAIRE color`);
        assert.equal(value.novaireStyle, 'normal', `${route} NOVAIRE style`);
        assert.equal(value.signalColor, 'rgb(181, 150, 98)', `${route} SIGNAL color`);
        assert.equal(value.signalStyle, 'italic', `${route} SIGNAL style`);
        assert.equal(value.globeAnimation, 'signal-gold-shimmer', `${route} globe animation`);
        assert.equal(value.globeDelay, '-0.72s', `${route} globe phase`);
        assert.equal(value.boltAnimation, 'signal-gold-shimmer', `${route} bolt animation`);
        assert.equal(value.boltDelay, '0s', `${route} bolt phase`);
        assert.deepEqual(value.links, ['/flaneur', '/', '/portfolio/'], `${route} brand links`);
        if (!baseline) baseline = value;
        else {
          for (const key of ['x', 'y', 'width', 'height']) {
            assert.ok(Math.abs(value.geometry[key] - baseline.geometry[key]) <= 0.75,
              `${route} ${key} parity: ${value.geometry[key]} vs ${baseline.geometry[key]}`);
          }
          assert.equal(value.fontFamily, baseline.fontFamily, `${route} font family parity`);
          assert.equal(value.fontSize, baseline.fontSize, `${route} font size parity`);
        }
        if (route === '/portfolio/daily/') {
          const daily = await page.evaluate(() => ({
            title: document.querySelector('.daily-title')?.textContent.trim(),
            titleColor: getComputedStyle(document.querySelector('.daily-title')).color,
            titleFamily: getComputedStyle(document.querySelector('.daily-title')).fontFamily,
            geopolitical: document.body.textContent.includes('Geopolitical pressure'),
            storyCount: document.querySelectorAll('.story').length,
          }));
          assert.equal(daily.title, 'The Daily.');
          assert.equal(daily.titleColor, 'rgb(255, 255, 255)');
          assert.match(daily.titleFamily, /Inter|system-ui/);
          assert.equal(daily.geopolitical, false);
          assert.equal(daily.storyCount, 0);
        }
        report[viewport.name][route] = value;
        await page.close();
      }
      await context.close();
    }
  } finally {
    await browser.close();
  }
  console.log(JSON.stringify({ ok: true, base: BASE, routes, viewports: Object.keys(report) }));
})().catch(error => { console.error(error.message); process.exit(1); });
