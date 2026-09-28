#!/usr/bin/env node
const { chromium } = require('/root/clawd/novaire-operations-system/node_modules/playwright');

const base = process.env.SIGNAL_BASE_URL || 'http://127.0.0.1:8765';
const routes = ['/', '/health/', '/map/', '/portfolio/', '/portfolio/daily/', '/portfolio/evolutionfund/', '/portfolio/evolutionfund/philosophy.html', '/portfolio/finances/', '/portfolio-lock.html'];
const widths = [320, 360, 375, 390, 1280];
const tolerance = 1.25;

(async () => {
  const browser = await chromium.launch({ headless: true, executablePath: '/snap/bin/chromium', args: ['--no-sandbox'] });
  const failures = [];
  const results = [];
  try {
    for (const width of widths) {
      const page = await browser.newPage({ viewport: { width, height: 900 } });
      for (const route of routes) {
        await page.goto(`${base}${route}`, { waitUntil: 'domcontentloaded' });
        await page.evaluate(() => document.fonts.ready);
        const rows = await page.locator('.signal-brand-row').evaluateAll((nodes) => nodes.map((node) => {
          const box = node.getBoundingClientRect();
          const parent = node.parentElement.getBoundingClientRect();
          const children = [...node.children].map((child) => {
            const rect = child.getBoundingClientRect();
            return { name: child.className, left: rect.left, right: rect.right };
          });
          return { left: box.left, right: box.right, width: box.width, center: (box.left + box.right) / 2, parentCenter: (parent.left + parent.right) / 2, children };
        }));
        if (rows.length !== 2) failures.push(`${route} @ ${width}: expected 2 rows, got ${rows.length}`);
        rows.forEach((row, index) => {
          if (row.left < -tolerance || row.right > width + tolerance) failures.push(`${route} @ ${width} row ${index}: bounds ${row.left.toFixed(2)}..${row.right.toFixed(2)}`);
          const gaps = row.children.slice(1).map((child, i) => child.left - row.children[i].right);
          if (gaps.some((gap) => gap < -tolerance)) failures.push(`${route} @ ${width} row ${index}: overlapping children ${gaps.map(x => x.toFixed(2)).join(',')}`);
        });
        if (rows.length === 2 && Math.abs(rows[0].width - rows[1].width) > tolerance) failures.push(`${route} @ ${width}: header/footer widths differ (${rows[0].width.toFixed(2)} vs ${rows[1].width.toFixed(2)})`);
        if (rows.length === 2 && Math.abs(rows[0].center - rows[1].center) > tolerance) failures.push(`${route} @ ${width}: header/footer centers differ (${rows[0].center.toFixed(2)} vs ${rows[1].center.toFixed(2)})`);
        results.push({ route, width, rows: rows.map(({ left, right, width }) => ({ left: +left.toFixed(2), right: +right.toFixed(2), width: +width.toFixed(2) })) });
      }
      await page.close();
    }
  } finally {
    await browser.close();
  }
  console.log(JSON.stringify(results, null, 2));
  if (failures.length) throw new Error(`Signal brand geometry failed:\n${failures.join('\n')}`);
  console.log(`PASS: ${routes.length} routes × ${widths.length} viewports; both rows bounded, centered, non-overlapping, and equal width.`);
})().catch((error) => { console.error(error.stack || error); process.exit(1); });