#!/usr/bin/env node
'use strict';
const {chromium}=require('/root/clawd/novaire-operations-system/node_modules/playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const base=process.env.BASE_URL||'https://novairesignal.com/';
const out=process.env.QA_OUT||'/root/.hermes/cache/scratch/headlines-live';
const ids=['zerohedge-card','signal-feed-card'];
const keys=['nv_zerohedge_state','nv_signal_feed_state'];
(async()=>{
 fs.mkdirSync(out,{recursive:true});
 const browser=await chromium.launch({executablePath:process.env.CHROMIUM_PATH||'/usr/bin/google-chrome',args:['--no-sandbox']});
 const results=[];
 try {
 for(const width of [1440,390,360]){
  const context=await browser.newContext({viewport:{width,height:1000},isMobile:width<600,hasTouch:width<600});
  const page=await context.newPage();
  await page.goto(base,{waitUntil:'domcontentloaded'});
  await page.waitForFunction(()=>!document.querySelector('#news-refresh').disabled&&!document.querySelector('#signal-refresh').disabled);
  for(const id of ids) assert.equal(await page.locator('#'+id).evaluate(e=>e.open),true);
  const images=[];
  for(const card of await page.locator('#zerohedge-feed .zh-feed-card').all()){
   await card.scrollIntoViewIfNeeded();
   const img=card.locator('img');
   if(await img.count()){
    await img.evaluate(e=>e.decode());
    const info=await img.evaluate(e=>({src:e.currentSrc,naturalWidth:e.naturalWidth,width:e.getBoundingClientRect().width,height:e.getBoundingClientRect().height}));
    assert.ok(info.naturalWidth>0);assert.ok(info.width<=90);images.push(info);
   }
  }
  assert.ok(images.length>0,'Current sourced article images must actually decode');
  const geometry=await page.evaluate(()=>['zerohedge-card','signal-feed-card'].map(id=>{
   const e=document.getElementById(id),r=e.getBoundingClientRect(),s=e.querySelector('summary'),t=s.querySelector('.card-title');
   const sr=s.getBoundingClientRect(),tr=t.getBoundingClientRect();
   return {id,width:r.width,left:r.left,right:r.right,titleInside:tr.left>=sr.left&&tr.right<=sr.right&&tr.top>=sr.top&&tr.bottom<=sr.bottom,overflow:document.documentElement.scrollWidth>innerWidth};
  }));
  for(const g of geometry){assert.ok(g.titleInside);assert.equal(g.overflow,false);assert.ok(g.right<=width+1);}
  await page.locator('#zerohedge-feed .feed-card-grid').evaluate(e=>e.scrollLeft=0);
  for(const id of ids) await page.locator('#'+id).screenshot({path:path.join(out,`${width}-${id}-open.png`)});
  const state=()=>page.evaluate(ids=>ids.map(id=>document.getElementById(id).open),ids);
  const waitStored=async values=>{await page.waitForFunction(({keys,values})=>keys.every((k,i)=>localStorage.getItem(k)===(values[i]?'open':'closed')),{keys,values});};
  // Keyboard is native; mixed independent choices must survive reload in both directions.
  await page.locator('#zerohedge-card>summary').focus();await page.keyboard.press('Enter');
  await page.waitForFunction(()=>!document.getElementById('zerohedge-card').open);
  await page.reload({waitUntil:'domcontentloaded'});await page.waitForTimeout(500);
  assert.deepEqual(await state(),[false,true]);
  await page.locator('#zerohedge-card>summary').focus();await page.keyboard.press('Space');
  await page.locator('#signal-feed-card>summary').click();
  await waitStored([true,false]);
  await page.reload({waitUntil:'domcontentloaded'});await page.waitForTimeout(500);
  assert.deepEqual(await state(),[true,false]);
  await page.locator('#signal-feed-card>summary').focus();await page.keyboard.press('Enter');
  await waitStored([true,true]);
  await page.waitForFunction(()=>!document.querySelector('#news-refresh').disabled&&!document.querySelector('#signal-refresh').disabled);
  await page.click('#news-refresh');await page.click('#signal-refresh');
  await page.waitForFunction(()=>!document.querySelector('#news-refresh').disabled&&!document.querySelector('#signal-refresh').disabled);
  assert.deepEqual(await state(),[true,true]);
  const refreshedImages=[];
  for(const img of await page.locator('#zerohedge-feed img').all()) {await img.scrollIntoViewIfNeeded();await img.evaluate(e=>e.decode());refreshedImages.push(await img.evaluate(e=>({src:e.currentSrc,naturalWidth:e.naturalWidth})));}
  await page.locator('#zerohedge-card>summary').click();await page.locator('#signal-feed-card>summary').click();
  await waitStored([false,false]);
  await page.evaluate(async()=>{await Promise.all([refreshZeroHedge(true),refreshSignals(true)]);});
  assert.deepEqual(await state(),[false,false]);
  await page.reload({waitUntil:'domcontentloaded'});await page.waitForTimeout(500);
  assert.deepEqual(await state(),[false,false]);
  for(const id of ids) await page.locator('#'+id).screenshot({path:path.join(out,`${width}-${id}-closed.png`)});
  results.push({width,images,refreshedImages,geometry,exactPersistence:true,keyboard:true,refreshPreservesParent:true});
  await context.close();
 }
 fs.writeFileSync(path.join(out,'results.json'),JSON.stringify({ok:true,base,results},null,2));
 console.log(JSON.stringify({ok:true,out,results},null,2));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
