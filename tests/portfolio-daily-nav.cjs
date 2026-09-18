const assert = require('node:assert/strict');
const path = require('node:path');
const { chromium } = require('/root/clawd/novaire-operations-system/node_modules/playwright');

(async () => {
  const browser = await chromium.launch({ headless: true });
  try {
    for (const viewport of [{ name: 'desktop', width: 1440, height: 900 }, { name: 'mobile', width: 393, height: 852 }]) {
      const page = await browser.newPage({ viewport });
      await page.goto(`file://${path.resolve(__dirname, '../portfolio/index.html')}`);
      const result = await page.evaluate(() => {
        const nav = document.querySelector('a.daily-nav-link[href="/portfolio/daily/"]');
        const icon = nav?.querySelector('svg.daily-nav-icon');
        const subtitle = [...document.querySelectorAll('.header-brand > div')].at(-1);
        const navRect = nav?.getBoundingClientRect();
        const iconRect = icon?.getBoundingClientRect();
        const subtitleRect = subtitle?.getBoundingClientRect();
        const containerRect = document.querySelector('.container').getBoundingClientRect();
        return {
          text: nav?.textContent.trim(),
          oldLabelPresent: document.body.textContent.includes('Portfolio Daily'),
          iconCount: nav?.querySelectorAll('svg.daily-nav-icon').length,
          iconColor: icon ? getComputedStyle(icon).color : null,
          gold: getComputedStyle(document.documentElement).getPropertyValue('--gold').trim(),
          iconWidth: icon ? getComputedStyle(icon).width : null,
          gap: iconRect && navRect ? Math.round((nav.querySelector('span').getBoundingClientRect().left - iconRect.right) * 10) / 10 : null,
          navRightDelta: navRect ? Math.round((containerRect.right - navRect.right) * 10) / 10 : null,
          subtitleCenterDelta: subtitleRect ? Math.round(((subtitleRect.left + subtitleRect.right) / 2 - (containerRect.left + containerRect.right) / 2) * 10) / 10 : null,
        };
      });
      assert.equal(result.text, 'Daily');
      assert.equal(result.oldLabelPresent, false);
      assert.equal(result.iconCount, 1);
      assert.equal(result.iconColor, 'rgb(181, 150, 98)');
      assert.equal(result.gold, '#b59662');
      assert(Math.abs(parseFloat(result.iconWidth) - 12) < 0.1, `${viewport.name}: icon width ${result.iconWidth}`);
      assert(result.gap >= 3.9 && result.gap <= 4.5, `${viewport.name}: icon gap ${result.gap}`);
      assert(Math.abs(result.navRightDelta) <= 1, `${viewport.name}: nav is not right aligned: ${result.navRightDelta}`);
      assert(Math.abs(result.subtitleCenterDelta) <= 1, `${viewport.name}: Portfolio subtitle is not centered: ${result.subtitleCenterDelta}`);
      await page.screenshot({ path: path.resolve(__dirname, `../qa-artifacts/portfolio-daily-nav-${viewport.name}.png`), fullPage: false });
      console.log(JSON.stringify({ viewport: viewport.name, ...result }));
    }
  } finally {
    await browser.close();
  }
})().catch((error) => { console.error(error); process.exit(1); });
