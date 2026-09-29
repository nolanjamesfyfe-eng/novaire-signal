import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import playwright from '/root/.hermes/cache/scratch/health-qa/node_modules/playwright-core/index.js';
const { chromium } = playwright;
const base = process.env.BRAIN_QA_URL || 'http://127.0.0.1:4177/tests/health-brain-fixture.html';
const shotDir = process.env.BRAIN_QA_SHOTS || '/root/.hermes/cache/scratch/health-brain-interaction';
const browser = await chromium.launch({ headless: true, executablePath: process.env.CHROME_BIN || '/usr/bin/google-chrome', args: ['--no-sandbox'] });
const delta = (a, b) => Math.hypot(...a.map((value, index) => value - b[index]));

try {
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, deviceScaleFactor: 1 });
  const page = await context.newPage();
  const errors = [];
  page.on('pageerror', error => errors.push(String(error)));
  await page.goto(base, { waitUntil: 'networkidle' });
  await page.waitForSelector('[data-brain-atlas][data-ready="true"]');
  const initial = await page.evaluate(() => ({
    ready: window.__HEALTH_BRAIN__.ready,
    distance: window.__HEALTH_BRAIN__.cameraDistance,
    selected: window.__HEALTH_BRAIN__.selected,
    level: window.__HEALTH_BRAIN__.level,
    labels: document.querySelectorAll('[data-brain-part]').length,
    copy: document.querySelector('.brain-atlas__signal p').textContent,
    turnButtons: document.querySelectorAll('[data-brain-turn]').length
  }));
  assert.equal(initial.ready, true);
  assert.equal(initial.labels, 6);
  assert.equal(initial.turnButtons, 2);
  assert.equal(initial.selected, null);
  assert.equal(initial.level, null);
  assert.match(initial.copy, /not measured brain activity/i);
  assert.match(initial.copy, /not.*diagnosis/i);
  assert.match(initial.copy, /regional function/i);
  assert.match(initial.copy, /inferred neuroscience/i);

  const expected = {
    frontal: /planning.*decision-making.*movement/i,
    parietal: /touch.*spatial attention/i,
    temporal: /hearing.*language.*memory/i,
    occipital: /visual processing.*color.*motion/i,
    cerebellum: /movement.*balance.*motor learning/i,
    brainstem: /breathing.*arousal.*vital/i
  };
  for (const [key, pattern] of Object.entries(expected)) {
    await page.locator(`[data-brain-part="${key}"]`).click();
    assert.equal(await page.evaluate(() => window.__HEALTH_BRAIN__.selected), key);
    const description = await page.locator('.brain-atlas__description').textContent();
    assert.match(description, pattern, `${key} needs functional copy`);
    assert.ok(description.split(/[.!?]+/).filter(Boolean).length <= 2, `${key} copy must remain at most two sentences`);
  }

  await page.evaluate(() => window.__HEALTH_BRAIN__.reset());
  const frontalPoint = await page.evaluate(() => window.__HEALTH_BRAIN__.findHitPoint('frontal'));
  assert.ok(frontalPoint, 'a visible frontal-lobe canvas point should be discoverable');
  await page.mouse.click(frontalPoint.x, frontalPoint.y);
  assert.equal(await page.evaluate(() => window.__HEALTH_BRAIN__.selected), 'frontal', 'actual canvas tap should select its visible structure');

  await page.locator('[data-brain-zoom="in"]').click();
  assert.ok(await page.evaluate(() => window.__HEALTH_BRAIN__.cameraDistance) < initial.distance, 'zoom in should reduce camera distance');
  await page.evaluate(() => window.__HEALTH_BRAIN__.reset());
  const turnBefore = await page.evaluate(() => window.__HEALTH_BRAIN__.cameraPose.position);
  await page.locator('[data-brain-turn="right"]').click();
  const turnAfter = await page.evaluate(() => window.__HEALTH_BRAIN__.cameraPose.position);
  assert.ok(delta(turnAfter, turnBefore) > 1, 'accessible turn control should materially change camera pose');

  await page.evaluate(() => window.__HEALTH_BRAIN__.reset());
  const poseBefore = await page.evaluate(() => window.__HEALTH_BRAIN__.cameraPose.position);
  const box = await page.locator('[data-brain-atlas] canvas').boundingBox();
  await page.mouse.move(box.x + box.width * .38, box.y + box.height * .5);
  await page.mouse.down();
  await page.mouse.move(box.x + box.width * .64, box.y + box.height * .45, { steps: 12 });
  await page.mouse.up();
  await page.waitForTimeout(180);
  const poseAfter = await page.evaluate(() => window.__HEALTH_BRAIN__.cameraPose.position);
  assert.ok(delta(poseAfter, poseBefore) > .5, 'mouse drag should produce an easy, material rotation');
  assert.equal(await page.evaluate(() => window.__HEALTH_BRAIN__.selected), null, 'drag must not become an accidental selection');

  await page.evaluate(() => document.dispatchEvent(new CustomEvent('health:checkin', { detail: { answers: { energy: 9, focus: 8, sleep: 8 } } })));
  await page.waitForTimeout(100);
  assert.ok(Math.abs(await page.evaluate(() => window.__HEALTH_BRAIN__.level) - .9) < .001);
  assert.match(await page.locator('[data-brain-signal]').textContent(), /90% · SELF-REPORTED/);
  await page.evaluate(() => document.dispatchEvent(new CustomEvent('health:checkin', { detail: null })));
  assert.equal(await page.evaluate(() => window.__HEALTH_BRAIN__.level), null);
  await page.evaluate(() => window.__HEALTH_BRAIN__.reset());
  await page.screenshot({ path: `${shotDir}/desktop.png`, fullPage: true });
  const pulse = [];
  for (let frame = 0; frame < 3; frame++) {
    await page.waitForTimeout(700);
    const path = `${shotDir}/pulse-${frame + 1}.png`;
    const image = await page.locator('[data-brain-atlas] canvas').screenshot({ path });
    pulse.push({ phase: await page.evaluate(() => window.__HEALTH_BRAIN__.pulsePhase), hash: createHash('sha256').update(image).digest('hex'), path });
  }
  assert.equal(new Set(pulse.map(frame => frame.hash)).size, 3, 'traveling illumination must produce perceptibly distinct rendered frames');
  assert.equal(new Set(pulse.map(frame => frame.phase.toFixed(3))).size, 3, 'pulse phase must advance between samples');
  assert.deepEqual(errors, []);
  await context.close();

  const mobileContext = await browser.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 1, isMobile: true, hasTouch: true });
  const mobile = await mobileContext.newPage();
  await mobile.goto(base, { waitUntil: 'networkidle' });
  await mobile.waitForSelector('[data-brain-atlas][data-ready="true"]');
  const collision = await mobile.evaluate(() => {
    const deck = document.querySelector('.brain-atlas__deck').getBoundingClientRect();
    const panel = document.querySelector('.brain-atlas__panel').getBoundingClientRect();
    const viewport = document.querySelector('.brain-atlas__viewport').getBoundingClientRect();
    const controls = [...document.querySelectorAll('.brain-atlas__turn,.brain-atlas__zoom')].map(node => node.getBoundingClientRect());
    const labels = document.querySelector('.brain-atlas__labels').getBoundingClientRect();
    return {
      overflow: document.documentElement.scrollWidth > innerWidth,
      panelOverlap: panel.top < viewport.bottom - 1,
      controlsInsideViewport: controls.every(rect => rect.top >= viewport.top && rect.bottom <= viewport.bottom + 1),
      labelsClearSwipeArea: labels.top >= viewport.bottom - 1,
      deckHeight: deck.height
    };
  });
  assert.equal(collision.overflow, false);
  assert.equal(collision.panelOverlap, false);
  assert.equal(collision.controlsInsideViewport, true);
  assert.equal(collision.labelsClearSwipeArea, true);

  const client = await mobileContext.newCDPSession(mobile);
  await client.send('Emulation.setTouchEmulationEnabled', { enabled: true, maxTouchPoints: 5 });
  const mobileBox = await mobile.locator('canvas').boundingBox();
  const cx = mobileBox.x + mobileBox.width / 2, cy = mobileBox.y + mobileBox.height * .57;
  const touch = (type, points) => client.send('Input.dispatchTouchEvent', { type, touchPoints: points.map((p, i) => ({ x: p.x, y: p.y, id: i + 1, radiusX: 2, radiusY: 2, force: .8 })) });
  const touchBefore = await mobile.evaluate(() => window.__HEALTH_BRAIN__.cameraPose.position);
  await touch('touchStart', [{ x: cx - 70, y: cy }]);
  await touch('touchMove', [{ x: cx + 72, y: cy - 16 }]);
  await touch('touchEnd', []);
  await mobile.waitForTimeout(220);
  const touchAfter = await mobile.evaluate(() => window.__HEALTH_BRAIN__.cameraPose.position);
  assert.ok(delta(touchAfter, touchBefore) > .5, 'native CDP touch drag should materially rotate camera');
  assert.equal(await mobile.evaluate(() => window.__HEALTH_BRAIN__.selected), null, 'touch drag must not select');

  const pinchBefore = await mobile.evaluate(() => window.__HEALTH_BRAIN__.cameraDistance);
  await touch('touchStart', [{ x: cx - 35, y: cy }, { x: cx + 35, y: cy }]);
  await touch('touchMove', [{ x: cx - 80, y: cy }, { x: cx + 80, y: cy }]);
  await touch('touchEnd', []);
  await mobile.waitForTimeout(220);
  const pinchAfter = await mobile.evaluate(() => window.__HEALTH_BRAIN__.cameraDistance);
  assert.ok(pinchAfter < pinchBefore - .1, 'native pinch-out should continue and zoom in');
  assert.equal(await mobile.evaluate(() => window.__HEALTH_BRAIN__.selected), null, 'pinch must not select');

  await mobile.evaluate(() => window.__HEALTH_BRAIN__.reset());
  await mobile.locator('[data-brain-part="brainstem"]').tap();
  assert.match(await mobile.locator('.brain-atlas__description').textContent(), /breathing.*arousal/i);
  await mobile.screenshot({ path: `${shotDir}/mobile.png`, fullPage: true });
  await mobileContext.close();
  const reducedContext = await browser.newContext({ viewport: { width: 900, height: 700 }, reducedMotion: 'reduce' });
  const reduced = await reducedContext.newPage();
  await reduced.goto(base, { waitUntil: 'networkidle' });
  await reduced.waitForSelector('[data-brain-atlas][data-ready="true"]');
  const reducedA = await reduced.evaluate(() => window.__HEALTH_BRAIN__.pulsePhase);
  await reduced.waitForTimeout(900);
  const reducedB = await reduced.evaluate(() => window.__HEALTH_BRAIN__.pulsePhase);
  assert.equal(reducedA, reducedB, 'reduced motion must hold a static illumination phase');
  await reduced.screenshot({ path: `${shotDir}/reduced-motion.png`, fullPage: true });
  await reducedContext.close();
  console.log(JSON.stringify({ ok: true, descriptions: 6, canvasTap: true, mouseRotationDelta: delta(poseAfter, poseBefore), touchRotationDelta: delta(touchAfter, touchBefore), pinchDistance: [pinchBefore, pinchAfter], checkinResponse: true, pulse, reducedMotionPhase: reducedA, mobile: collision, screenshots: [`${shotDir}/desktop.png`, `${shotDir}/mobile.png`, `${shotDir}/reduced-motion.png`] }));
} finally {
  await browser.close();
}
