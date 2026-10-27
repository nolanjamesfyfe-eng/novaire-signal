#!/usr/bin/env node
'use strict';
// Compare the approved committed HTML with regenerated HTML at mouse/PC widths.
const {chromium}=require('/root/clawd/novaire-operations-system/node_modules/playwright');
const fs=require('node:fs');const assert=require('node:assert/strict');const {execFileSync}=require('node:child_process');
(async()=>{
 const old=process.env.FED_BASELINE_HTML ? fs.readFileSync(process.env.FED_BASELINE_HTML,'utf8') : execFileSync('git',['show','HEAD:index.html'],{encoding:'utf8',maxBuffer:8e6});
 const current=fs.readFileSync('index.html','utf8');
 const output=process.env.QA_OUTPUT_DIR || '/root/.hermes/cache/images/fed-desktop-v2';fs.mkdirSync(output,{recursive:true});
 const browser=await chromium.launch({executablePath:'/snap/bin/chromium',args:['--no-sandbox']});const results=[];
 try{for(const width of [760,980,1100,1440]){
  const samples=[];
  for(const [name,html] of [['before',old],['after',current]]){
   const page=await browser.newPage({viewport:{width,height:1000},hasTouch:false});
   await page.route('**/*',r=>r.request().resourceType()==='script'?r.abort():r.continue());
   await page.setContent(html.replace(/<script\b[^>]*>[\s\S]*?<\/script>/gi,''),{waitUntil:'domcontentloaded'});
   await page.evaluate(()=>document.fonts.ready);await page.locator('#fed-signal-card').evaluate(e=>e.open=true);
   samples.push(await page.locator('#fed-signal-card').evaluate(card=>[card,...card.querySelectorAll('*')].map(e=>{const s=getComputedStyle(e),r=e.getBoundingClientRect();return {tag:e.tagName,cls:e.className,width:r.width,height:r.height,left:r.left-card.getBoundingClientRect().left,top:r.top-card.getBoundingClientRect().top,style:[...s].sort().map(k=>[k,s.getPropertyValue(k)])}})));
   await page.locator('#fed-signal-card').screenshot({path:`${output}/${width}-${name}.png`});await page.close();
  }
  assert.deepEqual(samples[1],samples[0],`${width}px desktop changed`);results.push({width,allComputedStylesAndRelativeRectsIdentical:true});
 }}finally{await browser.close()}
 console.log(JSON.stringify({ok:true,results},null,2));
})().catch(e=>{console.error(e);process.exit(1)});
