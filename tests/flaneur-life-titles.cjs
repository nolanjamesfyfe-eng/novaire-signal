// Run: node tests/flaneur-life-titles.cjs [URL or file://.../index.html]
const assert = require('node:assert/strict');
const path = require('node:path');
const fs = require('node:fs');
const puppeteer = require('/root/clawd/node_modules/puppeteer');
const url = process.argv[2] || `file://${path.resolve(__dirname, '../index.html')}`;
const out = process.env.QA_OUT || '/root/.hermes/cache/images/flaneur-life-titles';
(async () => {
  fs.mkdirSync(out, {recursive:true});
  const browser = await puppeteer.launch({executablePath:'/usr/bin/google-chrome',headless:true,args:['--no-sandbox']});
  const results = [];
  try {
    for (const width of [360,375,390,430,1440]) {
      const page = await browser.newPage();
      await page.setViewport({width,height:1000});
      await page.goto(url, {waitUntil:'networkidle2'});
      await page.evaluate(async()=>{await document.fonts.ready;document.querySelector('#world-tour-card').open=true;});
      const rows = await page.$$eval('#world-tour-card .countdown-item', items => items.map(e=>{
        const label=e.querySelector('.countdown-label'), range=document.createRange();range.selectNodeContents(label);
        const rect=r=>({x:r.x,y:r.y,width:r.width,height:r.height,right:r.right});
        return {text:label.textContent,href:e.href,item:rect(e.getBoundingClientRect()),label:rect(label.getBoundingClientRect()),ink:[...range.getClientRects()].map(rect),lineHeight:parseFloat(getComputedStyle(label).lineHeight),fontSize:getComputedStyle(label).fontSize};
      }));
      assert.equal(rows.length,3);
      assert.equal(rows[2].text,'Soviet Quest 🚂');
      assert.deepEqual(rows.map(r=>r.href),['https://thailand.edc.com/en/','https://manontherise.com/retreat','https://sovietsidequest.com/']);
      for(const r of rows){
        assert(Math.abs(r.label.y-rows[0].label.y)<1,`${width}: title tops differ`);
        assert(Math.abs(r.item.width-rows[0].item.width)<1,`${width}: columns unequal`);
        assert.equal(new Set(r.ink.map(i=>Math.round(i.y))).size,1,`${width}: wrapped ${r.text}`);
        assert(r.ink.every(i=>i.x>=r.item.x-1 && i.right<=r.item.right+1),`${width}: text escaped ${r.text}`);
        assert(Math.abs(r.label.x+r.label.width/2-r.item.x-r.item.width/2)<1,`${width}: off center`);
      }
      assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),`${width}: page overflow`);
      await (await page.$('#world-tour-card')).screenshot({path:path.join(out,`${width}.png`)});
      await page.click('#world-tour-card summary');
      assert.equal(await page.$eval('#world-tour-card',e=>e.open),false);
      // The native details toggle event is queued; let persistence finish.
      await new Promise(resolve=>setTimeout(resolve,200));
      await page.reload({waitUntil:'networkidle2'});
      assert.equal(await page.$eval('#world-tour-card',e=>e.open),false,'closed accordion state must survive reload');
      results.push({width,rows,closedStatePreserved:true});
      await page.close();
    }
    fs.writeFileSync(path.join(out,'geometry.json'),JSON.stringify({url,results},null,2));
    console.log(JSON.stringify({url,widths:results.map(r=>r.width),passed:true,evidence:out}));
  } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
