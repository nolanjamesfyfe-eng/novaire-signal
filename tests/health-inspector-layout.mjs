import playwright from '/root/.hermes/cache/scratch/health-qa/node_modules/playwright-core/index.js';
import { spawn } from 'node:child_process';
import { strict as assert } from 'node:assert';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const { chromium } = playwright;
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const output = process.env.HEALTH_INSPECTOR_OUTPUT || path.join(root, 'tests', 'health-inspector-evidence');
const port = Number(process.env.HEALTH_INSPECTOR_PORT || 4193);
fs.mkdirSync(output, { recursive: true });
const tmp = process.env.HEALTH_INSPECTOR_TMPDIR || path.join(root, 'tests', '.pw-tmp');
fs.mkdirSync(tmp, { recursive: true });
process.env.TMPDIR = tmp;
const server = spawn('python3', ['-m', 'http.server', String(port), '--bind', '127.0.0.1'], {
  cwd: root,
  env: { ...process.env, TMPDIR: tmp },
  stdio: 'ignore'
});

const geometry = () => {
  const rect = element => {
    const value = element.getBoundingClientRect();
    return { x: value.x, y: value.y, width: value.width, height: value.height, right: value.right, bottom: value.bottom };
  };
  const q = selector => document.querySelector(selector);
  const stage = rect(q('.stage'));
  const viewport = rect(q('#viewport'));
  const inspector = rect(q('#inspector'));
  const title = rect(q('#muscle-name'));
  const meta = rect(q('#muscle-meta'));
  const rows = [...document.querySelectorAll('.data-row')].map(rect);
  const button = rect(q('#focus-button'));
  const style = getComputedStyle(q('#inspector'));
  return {
    stage, viewport, inspector, title, meta, rows, button,
    gap: inspector.x - viewport.right,
    rightGutter: stage.right - inspector.right,
    titleOverflow: q('#muscle-name').scrollWidth - q('#muscle-name').clientWidth,
    inspectorOverflow: q('#inspector').scrollHeight - q('#inspector').clientHeight,
    paddingLeft: parseFloat(style.paddingLeft),
    paddingRight: parseFloat(style.paddingRight),
    scrollWidth: document.documentElement.scrollWidth,
    clientWidth: document.documentElement.clientWidth
  };
};

await new Promise(resolve => setTimeout(resolve, 700));
let browser;
try {
  browser = await chromium.launch({ headless: true, executablePath: '/snap/bin/chromium', args: ['--no-sandbox'] });
  for (const viewport of [
    { name: 'reference-desktop', width: 2332, height: 1486 },
    { name: 'laptop', width: 1440, height: 918 },
    { name: 'compact-laptop', width: 1280, height: 800 }
  ]) {
    const page = await browser.newPage({ viewport: { width: viewport.width, height: viewport.height }, deviceScaleFactor: 1 });
    await page.goto(`http://127.0.0.1:${port}/health/`, { waitUntil: 'domcontentloaded', timeout: 120000 });
    await page.waitForFunction(() => window.__HEALTH_ATLAS__?.ready === true, null, { timeout: 120000 });
    const empty = await page.evaluate(geometry);
    assert.ok(empty.gap >= 16, `${viewport.name}: inspector must clear the stage by >=16px; got ${empty.gap}`);
    assert.ok(empty.rightGutter >= 20, `${viewport.name}: right gutter must be >=20px; got ${empty.rightGutter}`);
    assert.ok(empty.inspector.height < 500, `${viewport.name}: inspector must be content-sized, not vertically stretched; got ${empty.inspector.height}`);
    assert.ok(empty.inspector.y >= empty.stage.y && empty.inspector.bottom <= empty.stage.bottom, `${viewport.name}: empty inspector clipped outside stage`);
    assert.equal(empty.titleOverflow <= 1, true, `${viewport.name}: empty title overflows`);
    assert.ok(empty.paddingLeft >= 20 && empty.paddingRight >= 20, `${viewport.name}: inspector lacks balanced inner gutters`);
    assert.ok(Math.abs(empty.title.x - empty.meta.x) <= 1, `${viewport.name}: heading and detail are not left-aligned`);
    assert.ok(Math.abs(empty.button.x - empty.title.x) <= 1 && Math.abs(empty.button.right - empty.title.right) <= 1, `${viewport.name}: button is not aligned with heading`);
    await page.screenshot({ path: path.join(output, `${viewport.name}-empty.png`), fullPage: false });

    const pickPoint = await page.evaluate(() => window.__HEALTH_ATLAS__.project('pectoralis'));
    assert.ok(pickPoint, `${viewport.name}: pectoralis is not projectable for pointer picking`);
    await page.mouse.click(pickPoint.x, pickPoint.y);
    await page.waitForFunction(() => window.__HEALTH_ATLAS__.selected === 'pectoralis');

    const selected = await page.evaluate(() => {
      const items = [...document.querySelectorAll('.muscle-item')];
      const item = items.sort((a, b) => b.textContent.trim().length - a.textContent.trim().length)[0];
      item?.click();
      return item?.textContent.trim() || '';
    });
    assert.ok(selected, `${viewport.name}: no selectable anatomy entries`);
    await page.waitForFunction(() => document.querySelector('#muscle-name').textContent !== 'Select a structure');
    const chosen = await page.evaluate(geometry);
    assert.ok(chosen.gap >= 16, `${viewport.name}: selected inspector overlaps stage`);
    assert.equal(chosen.titleOverflow <= 1, true, `${viewport.name}: selected long title overflows`);
    assert.ok(chosen.inspectorOverflow <= 1, `${viewport.name}: selected inspector content clips vertically`);
    assert.ok(chosen.title.bottom <= chosen.meta.y + 1, `${viewport.name}: selected heading collides with details`);
    assert.equal(await page.locator('#focus-button').isEnabled(), true, `${viewport.name}: selected structure focus is disabled`);
    const beforeFocus = await page.evaluate(() => window.__HEALTH_ATLAS__.state.camera);
    await page.locator('#focus-button').click();
    await page.waitForTimeout(700);
    const afterFocus = await page.evaluate(() => window.__HEALTH_ATLAS__.state.camera);
    assert.notDeepEqual(afterFocus, beforeFocus, `${viewport.name}: focus did not move the camera`);
    await page.screenshot({ path: path.join(output, `${viewport.name}-selected.png`), fullPage: false });
    await page.close();
  }

  for (const viewport of [
    { name: 'mobile-390', width: 390, height: 844 },
    { name: 'mobile-360', width: 360, height: 800 }
  ]) {
    const page = await browser.newPage({ viewport: { width: viewport.width, height: viewport.height }, deviceScaleFactor: 1 });
    await page.goto(`http://127.0.0.1:${port}/health/`, { waitUntil: 'domcontentloaded', timeout: 120000 });
    await page.waitForFunction(() => window.__HEALTH_ATLAS__?.ready === true, null, { timeout: 120000 });
    await page.evaluate(() => {
      const items = [...document.querySelectorAll('.muscle-item')];
      items.sort((a, b) => b.textContent.trim().length - a.textContent.trim().length)[0]?.click();
    });
    await page.waitForFunction(() => document.querySelector('#muscle-name').textContent !== 'Select a structure');
    const chosen = await page.evaluate(geometry);
    assert.ok(chosen.inspector.x >= 10 && chosen.inspector.right <= chosen.stage.right - 10, `${viewport.name}: inspector breaches side gutters`);
    assert.ok(chosen.inspector.y >= chosen.viewport.bottom + 10, `${viewport.name}: inspector overlaps the anatomy viewport`);
    assert.ok(chosen.inspector.bottom <= chosen.stage.bottom - 8, `${viewport.name}: inspector clips below stage`);
    assert.equal(chosen.titleOverflow <= 1, true, `${viewport.name}: selected long title overflows`);
    assert.ok(chosen.inspectorOverflow <= 1, `${viewport.name}: selected inspector content clips`);
    assert.equal(chosen.scrollWidth, chosen.clientWidth, `${viewport.name}: horizontal overflow`);
    await page.screenshot({ path: path.join(output, `${viewport.name}-selected.png`), fullPage: false });
    await page.close();
  }
  console.log(`PASS health inspector layout: desktop stage clearance, balanced gutters/alignment, selected long-title fit, and narrow mobile clipping checks; screenshots=${output}`);
} finally {
  if (browser) await browser.close();
  server.kill('SIGTERM');
}
