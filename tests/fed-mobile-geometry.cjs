#!/usr/bin/env node
'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require('/root/clawd/novaire-operations-system/node_modules/playwright');

const BASE = (process.env.NOVAIRE_SIGNAL_BASE_URL || 'http://127.0.0.1:8765').replace(/\/$/, '');
const OUTPUT = process.env.QA_OUTPUT_DIR || path.resolve(__dirname, '..', 'qa-artifacts', 'fed-mobile-geometry');
const VIEWPORTS = [320, 360, 375, 390, 430];
const TEXT_SCALES = [1, 2];

(async () => {
  fs.mkdirSync(OUTPUT, { recursive: true });
  const browser = await chromium.launch({
    headless: true,
    executablePath: process.env.CHROMIUM_PATH || '/snap/bin/chromium',
    args: ['--no-sandbox'],
  });
  const observations = [];
  try {
    for (const width of VIEWPORTS) {
      for (const textScale of TEXT_SCALES) {
        const context = await browser.newContext({ viewport: { width, height: 900 } });
        const page = await context.newPage();
        await page.goto(`${BASE}/?fed_geometry=${width}-${textScale}-${Date.now()}`, { waitUntil: 'networkidle', timeout: 60000 });
        const result = await page.evaluate(({ textScale }) => {
          if (textScale === 2) document.documentElement.style.fontSize = '220%';
          const card = document.querySelector('#fed-signal-card');
          assertCard(card);
          card.open = true;
          const summary = card.querySelector(':scope > summary');
          const body = card.querySelector(':scope > .signal-accordion-body');
          const grid = body.querySelector('.fed-stats');
          const items = [...grid.children];
          const rect = element => {
            const value = element.getBoundingClientRect();
            return { left: value.left, top: value.top, right: value.right, bottom: value.bottom, width: value.width, height: value.height };
          };
          const overflows = element => element.scrollWidth > element.clientWidth + 1 || element.scrollHeight > element.clientHeight + 1;
          const contained = (outer, inner) => inner.left >= outer.left - 1 && inner.right <= outer.right + 1 && inner.top >= outer.top - 1 && inner.bottom <= outer.bottom + 1;
          const intersects = (a, b) => Math.min(a.right, b.right) - Math.max(a.left, b.left) > 0.5 && Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top) > 0.5;
          const collisions = [];
          const escaped = [];
          for (const item of items) {
            const itemRect = rect(item);
            const blocks = [...item.querySelectorAll(':scope > span, :scope > b, :scope > em')];
            blocks.forEach(block => {
              if (!contained(itemRect, rect(block)) || overflows(block)) escaped.push(block.innerText.trim());
            });
            for (let i = 0; i < blocks.length; i += 1) {
              for (let j = i + 1; j < blocks.length; j += 1) {
                if (intersects(rect(blocks[i]), rect(blocks[j]))) collisions.push(`${blocks[i].innerText.trim()} <> ${blocks[j].innerText.trim()}`);
              }
            }
            const probabilityValues = [...item.querySelectorAll(':scope > b > i')];
            probabilityValues.forEach(value => {
              if (!contained(itemRect, rect(value)) || overflows(value)) escaped.push(value.innerText.trim());
            });
            if (probabilityValues.length === 2 && intersects(rect(probabilityValues[0]), rect(probabilityValues[1]))) {
              collisions.push(`${probabilityValues[0].innerText.trim()} <> ${probabilityValues[1].innerText.trim()}`);
            }
          }
          return {
            viewport: { width: innerWidth, clientWidth: document.documentElement.clientWidth, pageOverflow: document.documentElement.scrollWidth - document.documentElement.clientWidth },
            textScale,
            columns: getComputedStyle(grid).gridTemplateColumns,
            rows: getComputedStyle(grid).gridTemplateRows,
            card: { rect: rect(card), overflow: overflows(card), scrollHeight: card.scrollHeight, clientHeight: card.clientHeight },
            body: { rect: rect(body), overflow: overflows(body), scrollHeight: body.scrollHeight, clientHeight: body.clientHeight },
            summary: { rect: rect(summary), overflow: overflows(summary), scrollWidth: summary.scrollWidth, clientWidth: summary.clientWidth },
            itemRects: items.map(rect),
            escaped: [...new Set(escaped)],
            collisions,
            order: items.map(item => item.querySelector('span').innerText.trim()),
          };
          function assertCard(value) { if (!value) throw new Error('Fed card missing'); }
        }, { textScale });

        assert.deepEqual(result.order, ['RATE', 'LAST MEETING', 'NEXT FOMC', 'CME FEDWATCH'], `${width}px/${textScale}x: approved order`);
        assert.equal(result.itemRects.length, 4, `${width}px/${textScale}x: four Fed cells`);
        assert.equal(result.columns.split(' ').length, textScale === 1 ? 2 : 1, `${width}px/${textScale}x: responsive mobile grid`);
        assert.ok(result.summary.rect.height >= 44, `${width}px/${textScale}x: summary tap target is ${result.summary.rect.height}px`);
        if (textScale === 1) assert.equal(result.viewport.pageOverflow, 0, `${width}px/${textScale}x: page overflow`);
        assert.equal(result.card.overflow, false, `${width}px/${textScale}x: clipped card content`);
        assert.equal(result.body.overflow, false, `${width}px/${textScale}x: clipped body content`);
        assert.equal(result.summary.overflow, false, `${width}px/${textScale}x: clipped compact header`);
        assert.deepEqual(result.escaped, [], `${width}px/${textScale}x: content escaped its cell`);
        assert.deepEqual(result.collisions, [], `${width}px/${textScale}x: intersecting text rectangles`);

        await page.locator('#fed-signal-card').scrollIntoViewIfNeeded();
        await page.screenshot({ path: path.join(OUTPUT, `fed-${width}-${textScale}x.png`), fullPage: false });
        observations.push({ width, ...result });
        await context.close();
      }
    }
  } finally {
    await browser.close();
  }
  console.log(JSON.stringify({ ok: true, observations, screenshots: OUTPUT }, null, 2));
})().catch(error => { console.error(error.stack || error.message); process.exit(1); });
