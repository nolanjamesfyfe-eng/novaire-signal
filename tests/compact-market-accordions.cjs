#!/usr/bin/env node
'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require('/root/clawd/novaire-operations-system/node_modules/playwright');

const BASE = (process.env.NOVAIRE_SIGNAL_BASE_URL || 'http://127.0.0.1:8765').replace(/\/$/, '');
const IDS = ['weekly-asymmetric-ideas', 'catalysts-card', 'fed-signal-card', 'polymarket-card', 'darvas-card'];
const outputDir = process.env.QA_OUTPUT_DIR || path.resolve(__dirname, '..', 'qa-artifacts', 'compact-weekly-scan');

(async () => {
  fs.mkdirSync(outputDir, { recursive: true });
  const browser = await chromium.launch({headless: true, executablePath: process.env.CHROMIUM_PATH || '/snap/bin/chromium', args: ['--no-sandbox']});
  const observations = [];
  try {
    for (const viewport of [
      {name:'desktop-1440', width:1440, height:1200},
      {name:'mobile-390', width:390, height:1000},
      {name:'mobile-360', width:360, height:1000},
    ]) {
      const context = await browser.newContext({viewport:{width:viewport.width,height:viewport.height}});
      const page = await context.newPage();
      await page.goto(`${BASE}/?compact_qa=${viewport.name}-${Date.now()}`, {waitUntil:'networkidle', timeout:60000});
      const result = await page.evaluate(ids => {
        const cards = ids.map(id => document.getElementById(id));
        if (cards.some(card => !card)) throw new Error(`missing scoped card: ${ids[cards.findIndex(card => !card)]}`);
        const exact = 'Nothing new. No verified scan is completed. No claim has been made.';
        const weekly = cards[0];
        weekly.open = true;
        cards.slice(1).forEach(card => card.open = false);
        const current = cards.map(card => ({id:card.id, open:card.open, height:card.getBoundingClientRect().height, summaryHeight:card.querySelector(':scope>summary').getBoundingClientRect().height}));
        const style = document.createElement('style');
        style.id = 'pre-fix-accordion-baseline';
        style.textContent = window.innerWidth >= 761 ? '.card.compact-market-accordion{padding:22px}' : '';
        document.head.appendChild(style);
        const baseline = cards.map(card => ({id:card.id, height:card.getBoundingClientRect().height, summaryHeight:card.querySelector(':scope>summary').getBoundingClientRect().height}));
        style.remove();
        return {
          current, baseline,
          exactFallbackCount: document.body.innerText.split(exact).length - 1,
          weeklyBodyText: weekly.querySelector(':scope>.signal-accordion-body').innerText.trim(),
          overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
          scopedCount: document.querySelectorAll('details.compact-market-accordion').length,
          unrelatedScoped: Boolean(document.querySelector('#world-tour-card.compact-market-accordion,#quotes-card.compact-market-accordion,#thailand-news-card.compact-market-accordion')),
        };
      }, IDS);
      assert.equal(result.scopedCount, 5, `${viewport.name}: exactly five compact accordions`);
      assert.equal(result.unrelatedScoped, false, `${viewport.name}: unrelated accordions changed`);
      assert.equal(result.exactFallbackCount, 1, `${viewport.name}: exact fallback count`);
      assert.equal(result.weeklyBodyText, 'Nothing new. No verified scan is completed. No claim has been made.', `${viewport.name}: Weekly fallback body`);
      assert.ok(result.overflow <= 0, `${viewport.name}: horizontal overflow ${result.overflow}px`);
      if (viewport.width >= 761) {
        result.current.slice(1).forEach((card, offset) => {
          const i = offset + 1;
          const reduction = 1 - card.height / result.baseline[i].height;
          assert.ok(reduction >= .39 && reduction <= .62, `${card.id}: ${(reduction*100).toFixed(1)}% desktop reduction is not roughly half`);
        });
        assert.ok(result.current[0].height <= 110, `expanded Weekly remains too tall: ${result.current[0].height}px`);
      }
      observations.push({viewport:viewport.name, ...result});
      await page.locator('#weekly-asymmetric-ideas').scrollIntoViewIfNeeded();
      await page.screenshot({path:path.join(outputDir, `${viewport.name}.png`), fullPage:false});

      for (const id of IDS) await page.locator(`#${id}`).evaluate(card => card.open = false);
      await page.waitForTimeout(100);
      await page.reload({waitUntil:'networkidle'});
      for (const id of IDS) assert.equal(await page.locator(`#${id}`).evaluate(card => card.open), false, `${viewport.name}: ${id} close persisted`);
      for (const id of IDS) await page.locator(`#${id}`).evaluate(card => card.open = true);
      await page.waitForTimeout(100);
      await page.reload({waitUntil:'networkidle'});
      for (const id of IDS) assert.equal(await page.locator(`#${id}`).evaluate(card => card.open), true, `${viewport.name}: ${id} open persisted`);
      await context.close();
    }
  } finally { await browser.close(); }
  console.log(JSON.stringify({ok:true, observations, screenshots:outputDir}, null, 2));
})().catch(error => { console.error(error.stack || error.message); process.exit(1); });
