const { chromium } = require('/tmp/quote-studio-qa/node_modules/playwright');
const assert = require('node:assert/strict');

(async () => {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 390, height: 844 }, acceptDownloads: true, permissions: ['clipboard-read', 'clipboard-write'] });
  const page = await context.newPage();
  const errors = [], posts = [];
  page.on('pageerror', e => errors.push(String(e)));
  await page.route('**/api/quote-post', async route => {
    if (route.request().method() === 'GET') return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ configured: true, account: 'Novairecito', authenticated: true }) });
    const body = route.request().postDataJSON(); posts.push(body);
    return route.fulfill({ status: 502, contentType: 'application/json', body: JSON.stringify({ error: 'ambiguous mocked failure' }) });
  });
  await page.goto('http://127.0.0.1:8767/', { waitUntil: 'domcontentloaded' });
  assert.equal(await page.locator('#med-collapse').count(), 0);
  const bolts = page.locator('[data-share-kind]'); assert.equal(await bolts.count(), 2);
  for (const id of ['#med-share-trigger', '#quote-share-trigger']) {
    const box = await page.locator(id).boundingBox(), parent = await page.locator(id).locator('..').boundingBox();
    assert.ok(box.x + box.width > parent.x + parent.width - 45 && box.y + box.height > parent.y + parent.height - 45, `${id} is not bottom-right`);
  }
  await page.locator('#meditation-daily > summary').click(); assert.equal(await page.locator('#meditation-daily').getAttribute('open'), null);
  await page.locator('#meditation-daily > summary').click(); assert.notEqual(await page.locator('#meditation-daily').getAttribute('open'), null);

  const longProse = Array.from({length: 18}, (_,i) => `Original editorial sentence ${i+1} about attention and judgment.`).join(' ');
  await page.evaluate(text => {
    document.querySelector('#med-title').textContent = 'The discipline of attention';
    document.querySelector('#med-excerpt').textContent = text;
    window.__drawn=[]; const original=CanvasRenderingContext2D.prototype.fillText;
    CanvasRenderingContext2D.prototype.fillText=function(text,...args){window.__drawn.push(String(text));return original.call(this,text,...args)};
  }, longProse);
  await page.click('#med-share-trigger');
  await page.waitForFunction(() => document.querySelector('#quote-share-status').textContent.includes('ready'));
  assert.equal(await page.locator('#quote-share-title').textContent(), 'Share to X?');
  assert.equal(await page.locator('#quote-post-preview').textContent(), 'Image only · @Novairecito');
  const medDrawn = await page.evaluate(() => window.__drawn.join(' '));
  assert.ok(medDrawn.includes('Original editorial sentence 18'));
  assert.ok(medDrawn.includes('Novairecito'));
  await page.evaluate(() => document.querySelector('#med-excerpt').textContent = 'MUTATED AFTER CLICK');
  await page.click('#quote-share-copy');
  assert.ok((await page.evaluate(() => navigator.clipboard.readText())).includes('Original editorial sentence 18'));
  assert.ok(!(await page.evaluate(() => navigator.clipboard.readText())).includes('MUTATED'));
  const storyReady = page.waitForFunction(() => document.querySelector('#quote-share-status').textContent.includes('ready'));
  await page.click('[data-quote-format="story"]'); await storyReady;
  const downloadEvent = page.waitForEvent('download'); await page.click('#quote-share-download');
  const download = await downloadEvent; assert.equal(download.suggestedFilename(), 'meditation-margin-1080x1920.png');
  await download.saveAs('/tmp/novaire-signal-meditation-story.png');
  assert.deepEqual(await page.evaluate(() => [document.querySelector('#quote-share-canvas').width, document.querySelector('#quote-share-canvas').height]), [1080,1920]);
  await page.keyboard.press('Escape');

  await page.evaluate(() => {
    document.querySelector('#qt-text').textContent='“Until you make the unconscious conscious, it will direct your life and you will call it fate.”';
    document.querySelector('#qt-auth').textContent='— Carl Jung'; window.__drawn=[];
  });
  await page.click('#quote-share-trigger'); await page.waitForFunction(() => document.querySelector('#quote-share-status').textContent.includes('ready'));
  const quoteDrawn=await page.evaluate(() => window.__drawn);
  assert.ok(quoteDrawn.includes('Carl Jung'));
  assert.ok(quoteDrawn.includes('Paraphrase · Aion, §126'));
  assert.ok(quoteDrawn.indexOf('Carl Jung') > quoteDrawn.findIndex(x => x.includes('Until you make')));
  assert.ok(quoteDrawn.indexOf('Paraphrase · Aion, §126') > quoteDrawn.indexOf('Carl Jung'));
  await page.click('#quote-post-confirm'); await page.waitForFunction(() => document.querySelector('#quote-post-status').textContent.includes('ambiguous mocked failure'));
  assert.equal(posts.length,1); assert.equal(posts[0].text,''); assert.equal(posts[0].confirmation,true); assert.match(posts[0].imageDataUrl,/^data:image\/png;base64,/);
  await page.keyboard.press('Escape'); await page.click('#quote-share-trigger'); await page.waitForFunction(() => document.querySelector('#quote-share-status').textContent.includes('ready'));
  assert.equal(await page.locator('#quote-post-confirm').isDisabled(),true); await page.locator('#quote-post-confirm').click({force:true});
  await page.waitForTimeout(100); assert.equal(posts.length,1);
  assert.deepEqual(errors, []);
  console.log('integrated dual-card image-only share QA: ok (snapshot, summary, story PNG, verified Jung metadata, mocked post only)');
  await browser.close();
})().catch(e => { console.error(e); process.exit(1); });
