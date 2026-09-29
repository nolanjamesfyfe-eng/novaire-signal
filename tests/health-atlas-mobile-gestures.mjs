import assert from 'node:assert/strict';
import fs from 'node:fs';
import {spawn} from 'node:child_process';
import playwright from '/root/.hermes/cache/scratch/health-qa/node_modules/playwright-core/index.js';

const root = new URL('..', import.meta.url).pathname;
const out = process.env.HEALTH_TOUCH_OUTPUT || '/root/.hermes/cache/scratch/health-touch-evidence';
const requestedLayer = process.env.HEALTH_TOUCH_LAYER || 'all';
const port = Number(process.env.HEALTH_TOUCH_PORT || 4192);
fs.mkdirSync(out, {recursive: true});
process.env.TMPDIR = root + 'tests/.pw-touch-tmp';
fs.mkdirSync(process.env.TMPDIR, {recursive: true});
const server = spawn('python3', ['-m', 'http.server', String(port), '--bind', '127.0.0.1'], {cwd: root, stdio: 'ignore'});
let browser;
const dist = state => Math.hypot(...state.camera.map((value, index) => value - state.target[index]));
const angleDelta = (a, b) => Math.atan2(Math.sin(b - a), Math.cos(b - a));
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));

async function touch(client, type, points, timestamp) {
  await client.send('Input.dispatchTouchEvent', {
    type,
    touchPoints: points.map(point => ({radiusX: 4, radiusY: 4, force: 1, ...point, x: Math.round(point.x), y: Math.round(point.y)})),
    modifiers: 0,
    ...(timestamp ? {timestamp} : {}),
  });
}
async function drag(client, from, to, id = 1, steps = 1) {
  await touch(client, 'touchStart', [{...from, id}]);
  for (let step = 1; step <= steps; step++) {
    const q = step / steps;
    await touch(client, 'touchMove', [{x: from.x + (to.x - from.x) * q, y: from.y + (to.y - from.y) * q, id}]);
  }
  await touch(client, 'touchEnd', []);
}
async function pinch(client, center, startRadius, endRadius, steps = 1, continueWithOne = null) {
  const points = radius => [
    {x: center.x - radius, y: center.y, id: 11},
    {x: center.x + radius, y: center.y, id: 12},
  ];
  await touch(client, 'touchStart', points(startRadius));
  for (let step = 1; step <= steps; step++) {
    const radius = startRadius + (endRadius - startRadius) * step / steps;
    await touch(client, 'touchMove', points(radius));
  }
  if (continueWithOne) {
    await touch(client, 'touchEnd', [{x: center.x - endRadius, y: center.y, id: 11}]);
    await touch(client, 'touchMove', [{x: continueWithOne.x, y: continueWithOne.y, id: 11}]);
  }
  await touch(client, 'touchEnd', []);
}
async function state(page) {
  await page.waitForTimeout(30);
  return page.evaluate(() => window.__HEALTH_ATLAS__.state);
}

for (let attempt = 0; attempt < 80; attempt++) {
  try { if ((await fetch(`http://127.0.0.1:${port}/health/`)).ok) break; } catch {}
  await sleep(100);
}
try {
  browser = await playwright.chromium.launch({headless: true, executablePath: '/snap/bin/chromium', args: ['--no-sandbox']});
  const context = await browser.newContext({viewport: {width: 390, height: 844}, deviceScaleFactor: 1, hasTouch: true, isMobile: true});
  const page = await context.newPage();
  await page.addInitScript(() => { window.requestAnimationFrame = callback => setTimeout(() => callback(performance.now()), 120); });
  const client = await context.newCDPSession(page);
  await client.send('Emulation.setDeviceMetricsOverride', {width: 390, height: 844, deviceScaleFactor: 1, mobile: true, screenWidth: 390, screenHeight: 844});
  await client.send('Emulation.setTouchEmulationEnabled', {enabled: true, maxTouchPoints: 2});
  const errors = [];
  page.on('pageerror', error => errors.push(String(error)));
  await page.goto(process.env.HEALTH_TOUCH_URL || `http://127.0.0.1:${port}/health/`, {waitUntil: 'domcontentloaded', timeout: 120000});
  await page.waitForFunction(() => window.__HEALTH_ATLAS__?.ready === true, null, {timeout: 120000});
  await page.evaluate(() => document.querySelector('#atlas-canvas').scrollIntoView({block: 'center', behavior: 'instant'}));
  await page.waitForTimeout(100);
  const canvas = page.locator('#atlas-canvas');
  const box = await page.evaluate(() => {
    const rect = document.querySelector('#atlas-canvas').getBoundingClientRect();
    return {x: rect.x, y: rect.y, width: rect.width, height: rect.height};
  });
  assert.ok(box && box.width > 200 && box.height > 300, 'canvas is visibly in the mobile viewport');
  await page.evaluate(() => {
    window.__touchEvidence = {pointerdown: 0, pointermove: 0, pointerup: 0, pointercancel: 0, touchstart: 0, touchmove: 0, touchend: 0, samples: []};
    const canvas = document.querySelector('#atlas-canvas');
    for (const type of Object.keys(window.__touchEvidence).filter(x => x !== 'samples')) document.addEventListener(type, event => {window.__touchEvidence[type]++; if (type.startsWith('pointer') && window.__touchEvidence.samples.length < 12) window.__touchEvidence.samples.push({type, x: event.pageX, y: event.pageY, pointerType: event.pointerType, id: event.pointerId, target: event.target?.id || event.target?.tagName});}, {passive: true, capture: true});
  });
  const center = {x: box.x + box.width / 2, y: box.y + box.height / 2};
  const clearHalfWidth = Math.min(45, box.width * .12);
  assert.equal(await page.evaluate(({x, y}) => document.elementFromPoint(x, y)?.id, center), 'atlas-canvas', 'gesture center targets the canvas');
  const layers = ['muscle', 'bone', 'skin'].filter(layer => requestedLayer === 'all' || requestedLayer === layer);
  const report = {environment: {viewport: {width: 390, height: 844}, hasTouch: true, isMobile: true, realHardware: false}, layers: {}};

  const touchTargets = await page.evaluate(() => Object.fromEntries(['.layer-controls button', '.view-controls button', '#zoom-in', '#zoom-out', '#close-inspector'].map(selector => {
    const rect = document.querySelector(selector).getBoundingClientRect(); return [selector, {width: rect.width, height: rect.height}];
  })));
  for (const [selector, rect] of Object.entries(touchTargets)) assert.ok(rect.width >= 44 && rect.height >= 44, `${selector} is at least 44px in both dimensions: ${JSON.stringify(rect)}`);

  const pec = await page.evaluate(() => window.__HEALTH_ATLAS__.verifiedRaycastPoint('pectoralis'));
  assert.ok(pec, 'pectoralis has a verified visible raycast point');
  assert.equal(await page.evaluate(({x, y}) => document.elementFromPoint(x, y)?.id, pec), 'atlas-canvas', 'native structure tap point targets the real canvas');
  await touch(client, 'touchStart', [{...pec, id: 70}]); await touch(client, 'touchEnd', []); await page.waitForTimeout(80);
  assert.equal(await page.evaluate(() => window.__HEALTH_ATLAS__.selected), 'pectoralis', 'single native tap selects a real structure');
  await page.evaluate(() => window.__HEALTH_ATLAS__.view('reset')); await page.waitForTimeout(100);
  const beforeSuppressedPinch = await state(page);
  await pinch(client, pec, 12, 30);
  await page.waitForTimeout(80);
  assert.equal(await page.evaluate(() => window.__HEALTH_ATLAS__.selected), null, 'multi-touch over a structure never selects it');
  assert.ok(dist(await state(page)) < dist(beforeSuppressedPinch), 'suppressed multi-touch still zooms');
  report.touchTargets = touchTargets;
  report.structureTap = {key: 'pectoralis', point: pec};

  for (const layer of layers) {
    await page.evaluate(layerName => document.querySelector(`[data-layer="${layerName}"]`).click(), layer);
    await page.evaluate(() => window.__HEALTH_ATLAS__.view('reset'));
    let baseline = await state(page);

    let previous = baseline;
    let azimuthTravel = 0;
    for (let n = 0; n < 10; n++) {
      await drag(client, {x: center.x + clearHalfWidth, y: center.y}, {x: center.x - clearHalfWidth, y: center.y}, 20 + n);
      const next = await state(page);
      azimuthTravel += Math.abs(angleDelta(previous.azimuth, next.azimuth));
      previous = next;
    }
    assert.ok(azimuthTravel >= Math.PI * 2, `${layer}: touch drag provides full-360 azimuth travel; got ${azimuthTravel}`);
    assert.equal(await page.evaluate(() => window.__HEALTH_ATLAS__.selected), null, `${layer}: drag does not pick anatomy`);

    const beforeVertical = previous;
    await drag(client, {x: center.x, y: box.y + box.height * .72}, {x: center.x, y: box.y + box.height * .28}, 40);
    const afterVertical = await state(page);
    assert.ok(Math.abs(afterVertical.polar - beforeVertical.polar) > .35, `${layer}: touch drag provides useful vertical orbit`);

    const beforePinchOut = afterVertical;
    await pinch(client, center, 18, 42);
    const afterPinchOut = await state(page);
    assert.ok(dist(afterPinchOut) < dist(beforePinchOut) - .25, `${layer}: pinch-out zooms in`);
    const beforePinchIn = afterPinchOut;
    await pinch(client, center, 42, 18);
    const afterPinchIn = await state(page);
    assert.ok(dist(afterPinchIn) > dist(beforePinchIn) + .25, `${layer}: pinch-in zooms out`);

    const beforeContinuity = afterPinchIn;
    await pinch(client, center, 18, 40, 1, {x: center.x - 44, y: center.y - 45});
    const afterContinuity = await state(page);
    assert.ok(Math.abs(angleDelta(beforeContinuity.azimuth, afterContinuity.azimuth)) > .08 || Math.abs(afterContinuity.polar - beforeContinuity.polar) > .08, `${layer}: two-pointer to one-pointer continuation orbits without reset`);
    assert.ok(dist(afterContinuity) >= .8 && dist(afterContinuity) <= 32, `${layer}: touch zoom remains clamped`);

    await page.screenshot({path: `${out}/mobile-${layer}-gesture.png`, clip: box});
    report.layers[layer] = {
      azimuthTravel,
      verticalPolarDelta: afterVertical.polar - beforeVertical.polar,
      pinchOut: [dist(beforePinchOut), dist(afterPinchOut)],
      pinchIn: [dist(beforePinchIn), dist(afterPinchIn)],
      continuation: {azimuthDelta: angleDelta(beforeContinuity.azimuth, afterContinuity.azimuth), polarDelta: afterContinuity.polar - beforeContinuity.polar},
      finalDistance: dist(afterContinuity),
    };
  }
  report.events = await page.evaluate(() => window.__touchEvidence);
  report.frameTiming = await page.evaluate(async () => {
    const samples = []; let last = performance.now();
    for (let i = 0; i < 10; i++) await new Promise(resolve => requestAnimationFrame(now => {samples.push(now - last); last = now; resolve();}));
    samples.sort((a, b) => a - b);
    return {median: samples[Math.floor(samples.length / 2)], p95: samples[Math.floor(samples.length * .95)], max: samples.at(-1)};
  });
  assert.ok(report.events.pointerdown > 0 && report.events.pointermove > 0, 'CDP touch generated pointer events on the canvas');
  assert.deepEqual(errors, []);
  fs.writeFileSync(`${out}/mobile-touch-report.json`, JSON.stringify(report, null, 2));
  console.log(JSON.stringify(report, null, 2));
  console.log(`PASS mobile atlas touch gestures; evidence=${out}`);
} finally {
  if (browser) await browser.close();
  server.kill('SIGTERM');
}
