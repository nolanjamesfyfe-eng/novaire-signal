#!/usr/bin/env node
const { chromium } = require('/root/clawd/novaire-operations-system/node_modules/playwright');
const fs = require('fs');
const assert = require('assert/strict');
const base = process.env.SIGNAL_BASE_URL || 'https://novairesignal.com/';
const out = process.env.EVIDENCE_DIR || process.env.TMPDIR + '/signal-tagline';
const baseline = process.env.BASELINE ? JSON.parse(fs.readFileSync(process.env.BASELINE)) : null;
(async () => {
  fs.mkdirSync(out, {recursive:true});
  const browser = await chromium.launch({headless:true, executablePath:process.env.AGENT_BROWSER_EXECUTABLE_PATH || '/opt/google/chrome/chrome', args:['--no-sandbox']});
  const results=[];
  try {
    for (const width of [360,390,1440]) {
      const page=await browser.newPage({viewport:{width,height:900}, reducedMotion:'reduce'});
      await page.goto(base,{waitUntil:'load'});
      await page.evaluate(()=>document.fonts.ready);
      const data=await page.evaluate(()=>{
        const props=['fontFamily','fontWeight','fontStyle','fontSize','letterSpacing','textTransform','color','opacity','lineHeight'];
        const sample=e=>({text:e.textContent,styles:Object.fromEntries(props.map(k=>[k,getComputedStyle(e)[k]]))});
        const header=[...document.querySelectorAll('.header-brand div')].find(e=>e.textContent==='Deciphering through the noise.');
        const footer=document.querySelector('.footer-tagline');
        const range=document.createRange();range.selectNodeContents(footer);const r=range.getBoundingClientRect();
        return {width:innerWidth,zoom:getComputedStyle(document.body).zoom,header:sample(header),footer:sample(footer),overflow:document.documentElement.scrollWidth>innerWidth,taglineBounds:{left:r.left,right:r.right},brand:[...document.querySelectorAll('.signal-brand-row')].map(e=>({html:e.outerHTML,width:e.getBoundingClientRect().width,height:e.getBoundingClientRect().height})),links:[...document.querySelectorAll('.footer a')].map(e=>[e.textContent,e.getAttribute('href')])};
      });
      results.push(data);
      await page.locator('.header-brand').screenshot({path:`${out}/header-${width}.png`});
      await page.locator('.footer').screenshot({path:`${out}/footer-${width}.png`});
      if(!process.env.RECORD_ONLY){
        assert.deepEqual(data.footer,data.header,`tagline parity @${width}`);
        assert.equal(data.header.text,'Deciphering through the noise.');
        assert.equal(data.overflow,false);
        assert(data.taglineBounds.left>=0 && data.taglineBounds.right<=width);
        if(baseline){const old=baseline.find(x=>x.width===width);assert.deepEqual(data.header,old.header);assert.deepEqual(data.brand,old.brand);assert.deepEqual(data.links,old.links);assert.equal(data.zoom,old.zoom);}
      }
      await page.close();
    }
  } finally {await browser.close();fs.writeFileSync(`${out}/results.json`,JSON.stringify(results,null,2));}
  console.log(JSON.stringify(results,null,2));
  console.log(process.env.RECORD_ONLY?'Baseline recorded':'PASS: exact tagline parity, no overflow, preserved header/brand/links at 360/390/1440');
})().catch(e=>{console.error(e);process.exit(1)});
