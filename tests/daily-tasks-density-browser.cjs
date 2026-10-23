const assert = require('node:assert/strict');
const fs = require('node:fs');
const http = require('node:http');
const path = require('node:path');
const { chromium } = require('/root/clawd/novaire-operations-system/node_modules/playwright');

const root = path.resolve(__dirname, '..');
const fixture = [
  'Talk to James: get Novairecito + Archimedes set up on Clips Pipeline',
  'Scuba diving in Phuket, for retreat, research this',
  'Make big MM mid September b4 Trip - Pastel? - make reserversation and post in Whatsapp chat.',
  'Customs office Tmrw afternoon - or Monday, bring PP',
  'Igor Interviews - go through',
];
const longFixture = [...fixture];
longFixture[2] = 'Write the complete unabridged launch handoff for the team, preserving every dependency, owner, deadline, rationale, exception, and verification step without clipping or truncating this sentence.';

function server() {
  return http.createServer((request, response) => {
    const pathname = new URL(request.url, 'http://local').pathname;
    const file = pathname === '/' ? 'index.html' : pathname.slice(1);
    const target = path.resolve(root, file);
    if (!target.startsWith(root + path.sep) || !fs.existsSync(target) || fs.statSync(target).isDirectory()) {
      response.writeHead(404).end('not found');
      return;
    }
    response.setHeader('content-type', file.endsWith('.html') ? 'text/html; charset=utf-8' : 'application/octet-stream');
    fs.createReadStream(target).pipe(response);
  });
}

function taskPayload(tasks = fixture) {
  return JSON.stringify({ok:true, listTitle:'Daily', tasks, fetchedAt:'2026-10-23T10:40:00.000Z', refreshState:'live'});
}

async function geometry(page) {
  return page.locator('#google-daily-tasks-card').evaluate(card => {
    const rows = [...card.querySelectorAll('.google-task-list li')];
    const summary = card.querySelector(':scope > summary');
    const meta = card.querySelector('.google-task-meta');
    return {
      cardHeight: card.getBoundingClientRect().height,
      summaryHeight: summary.getBoundingClientRect().height,
      metaHeight: meta.getBoundingClientRect().height,
      rowHeights: rows.map(row => row.getBoundingClientRect().height),
      titles: rows.map(row => row.querySelector('.google-task-title')?.textContent),
      clipped: rows.some(row => {
        const title = row.querySelector('.google-task-title');
        return row.scrollWidth > row.clientWidth + 1 || title.scrollWidth > title.clientWidth + 1 || title.scrollHeight > title.clientHeight + 1;
      }),
      controls: card.querySelectorAll('button,input,a,[role="button"]').length,
      fontSizes: rows.map(row => parseFloat(getComputedStyle(row).fontSize)),
      overflowX: document.documentElement.scrollWidth - document.documentElement.clientWidth,
      score: card.querySelector('.accordion-score').textContent,
      sync: card.querySelector('.google-task-sync').textContent,
      refresh: card.dataset.taskRefresh,
    };
  });
}

(async () => {
  const app = server();
  await new Promise(resolve => app.listen(0, '127.0.0.1', resolve));
  const base = `http://127.0.0.1:${app.address().port}/`;
  const browser = await chromium.launch({headless:true, executablePath:'/snap/bin/chromium', args:['--no-sandbox']});
  const results = {};
  try {
    for (const width of [1920, 390, 360]) {
      const context = await browser.newContext({viewport:{width, height:1200}});
      const page = await context.newPage();
      let releaseLive;
      const liveGate = new Promise(resolve => { releaseLive = resolve; });
      await page.route('**/api/google-tasks**', async route => {
        await liveGate;
        await route.fulfill({status:200, contentType:'application/json', body:taskPayload(width === 360 ? longFixture : fixture)});
      });
      await page.goto(base, {waitUntil:'domcontentloaded'});
      const initial = await geometry(page);
      assert.equal(initial.cardHeight <= (width > 560 ? 310 : 400), true, `${width}px initial snapshot is not compact: ${JSON.stringify(initial)}`);
      releaseLive();
      await page.waitForFunction(expected => document.querySelector('#google-daily-tasks-card .google-task-title')?.textContent === expected, (width === 360 ? longFixture : fixture)[0]);
      await page.waitForFunction(() => document.querySelector('#google-daily-tasks-card')?.dataset.taskRefresh === 'live');
      const live = await geometry(page);
      assert.deepEqual(live.titles, width === 360 ? longFixture : fixture, `${width}px task order/content changed`);
      assert.equal(live.controls, 0, `${width}px introduced task mutation controls`);
      assert.equal(live.clipped, false, `${width}px wrapped task text clipped or overflowed`);
      assert.equal(live.overflowX, 0, `${width}px document overflowed horizontally`);
      assert.equal(live.score, '5 incomplete');
      assert.equal(live.refresh, 'live');
      assert.match(live.sync, /^Google Tasks · Live /);
      assert.equal(Math.min(...live.fontSizes) >= 13.5, true, `${width}px task text became illegible`);
      assert.equal(live.cardHeight <= (width > 560 ? 290 : 400), true, `${width}px live-injected card is not compact`);
      if (width === 1920) {
        assert.equal(live.cardHeight >= 250, true, 'desktop card was compressed beyond the readable target');
        assert.equal(live.rowHeights.every(height => height >= 38 && height <= 42), true, `unexpected desktop row heights: ${live.rowHeights}`);
      }
      await page.locator('#google-daily-tasks-card > summary').click();
      await page.reload({waitUntil:'domcontentloaded'});
      assert.equal(await page.locator('#google-daily-tasks-card').evaluate(card => card.open), false, `${width}px closed state did not persist`);
      await page.locator('#google-daily-tasks-card > summary').click();
      await page.reload({waitUntil:'domcontentloaded'});
      assert.equal(await page.locator('#google-daily-tasks-card').evaluate(card => card.open), true, `${width}px open state did not persist`);
      const output = process.env.QA_OUTPUT_DIR;
      if (output) {
        fs.mkdirSync(output, {recursive:true});
        await page.locator('#google-daily-tasks-card').screenshot({path:path.join(output, `daily-tasks-local-${width}.png`)});
      }
      results[width] = {initial, live};
      await context.close();
    }

    const context = await browser.newContext({viewport:{width:390, height:844}});
    const page = await context.newPage();
    await page.route('**/api/google-tasks**', route => route.fulfill({status:502, contentType:'application/json', body:JSON.stringify({ok:false})}));
    await page.goto(base, {waitUntil:'networkidle'});
    const failed = await geometry(page);
    assert.equal(failed.refresh, 'stale');
    assert.match(failed.sync, /Live refresh unavailable · showing scheduled snapshot/);
    assert.equal(failed.controls, 0);
    assert.equal(failed.clipped, false);
    assert.equal(failed.cardHeight <= 400, true, 'error/snapshot state lost compact density');
    results.error390 = failed;
    await context.close();
    console.log(JSON.stringify(results, null, 2));
  } finally {
    await browser.close();
    await new Promise(resolve => app.close(resolve));
  }
})().catch(error => { console.error(error); process.exit(1); });
