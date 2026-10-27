#!/usr/bin/env node
'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const {chromium} = require('/root/clawd/novaire-operations-system/node_modules/playwright');
const allIds = ['latest-novaire-card','weekly-asymmetric-ideas','catalysts-card','fed-signal-card','polymarket-card','darvas-card','thailand-news-card','economies-card','google-daily-tasks-card'];
const base = process.env.NOVAIRE_SIGNAL_BASE_URL || 'http://127.0.0.1:8767';
const out = process.env.QA_OUTPUT_DIR || '/root/clawd/.worktrees/latest-compact/qa-artifacts/compact-closed';
(async()=>{
 fs.mkdirSync(out,{recursive:true});
 const browser = await chromium.launch({executablePath:process.env.CHROMIUM_PATH||'/snap/bin/chromium',args:['--no-sandbox']});
 const results=[];
 try {
 for(const width of [1440,1920,320,360,390]) for(const scale of [1,2]) {
  const context=await browser.newContext({viewport:{width,height:1000}}),page=await context.newPage();
  if(process.env.QA_INCLUDE_SEASONAL==='1') {
   // Test-only approved seasonal markup; never publish it off cadence.
   const html=fs.readFileSync(require('path').join(__dirname,'../index.html'),'utf8');
   const fixture=fs.readFileSync(require('path').join(__dirname,'fixtures/economies-closed-peer.html'),'utf8');
   await page.route(base,route=>route.fulfill({contentType:'text/html',body:html.includes('id="economies-card"')?html:html.replace('<!-- TOP 5 ECONOMIES -->','<!-- TOP 5 ECONOMIES -->'+fixture)}));
  }
  await page.goto(base,{waitUntil:'domcontentloaded'}); await page.waitForTimeout(1500);
  const ids=await page.evaluate(ids=>ids.filter(id=>document.getElementById(id)),allIds);
  const missing=allIds.filter(id=>!ids.includes(id));
  assert.ok(missing.length===0 || (process.env.QA_INCLUDE_SEASONAL!=='1' && missing.length===1 && missing[0]==='economies-card'),'only off-cadence Economies may be absent');
  const initial=await page.evaluate(ids=>ids.map(id=>document.getElementById(id).open),ids);
  assert.equal(initial[0],false,'Latest first visit remains closed');
  await page.evaluate(({ids,scale})=>{if(scale===2)document.documentElement.style.fontSize=(parseFloat(getComputedStyle(document.documentElement).fontSize)*2)+'px';ids.forEach(id=>document.getElementById(id).open=false)}, {ids,scale});
  await page.waitForTimeout(100);
  const geometry=await page.evaluate(ids=>ids.map(id=>{
   const e=document.getElementById(id),s=e.querySelector(':scope>summary'),r=e.getBoundingClientRect(),sr=s.getBoundingClientRect();
   const escaped=[];
   for(const node of s.querySelectorAll('*')){if(!node.getClientRects().length)continue;const x=node.getBoundingClientRect(); if(x.left<sr.left-1||x.right>sr.right+1||x.top<sr.top-1||x.bottom>sr.bottom+1||node.scrollWidth>node.clientWidth+1)escaped.push(node.className)}
   // Text ranges catch wrapped text escaping a box even when its element fits.
   const walker=document.createTreeWalker(s,NodeFilter.SHOW_TEXT);while(walker.nextNode()){if(!walker.currentNode.textContent.trim())continue;const range=document.createRange();range.selectNodeContents(walker.currentNode);for(const x of range.getClientRects())if(x.width&&(x.left<sr.left-1||x.right>sr.right-14||x.top<sr.top-1||x.bottom>sr.bottom+1))escaped.push(walker.currentNode.textContent)}
   const chevron=getComputedStyle(s,'::after');
   const icon=s.querySelector('.compact-peer-icon').getBoundingClientRect(),label=s.querySelector('.compact-peer-label').getBoundingClientRect();
   return {id,width:r.width,height:r.height,summary:sr.height,iconX:icon.left-r.left,labelX:label.left-r.left,escaped,chevron:{width:chevron.width,height:chevron.height,background:chevron.backgroundColor},title:s.querySelector('.card-title').textContent};
  }),ids);
  for(const key of ['iconX','labelX'])assert.ok(Math.max(...geometry.map(x=>x[key]))-Math.min(...geometry.map(x=>x[key]))<=1,`${width}/${scale}: identical ${key}`);
  assert.ok(Math.max(...geometry.map(x=>x.height))-Math.min(...geometry.map(x=>x.height))<=1,`${width}/${scale}: equal closed shells`);
  for(const x of geometry){assert.deepEqual(x.escaped,[],`${width}/${scale}/${x.id}: contained summary`);assert.ok(Math.abs(parseFloat(x.chevron.width)-10)<.1);assert.ok(Math.abs(parseFloat(x.chevron.height)-6)<.1);}
  if(scale===1&&width>=1440)assert.ok(Math.abs(geometry[0].height-43.796875)<=1,'compact existing Fed desktop baseline');
  for(const id of ids){
   const card=page.locator('#'+id),summary=card.locator(':scope>summary');
   await summary.focus();await page.keyboard.press('Enter');await page.waitForTimeout(80);assert.equal(await card.evaluate(e=>e.open),true);
   await summary.click();await page.waitForTimeout(80);assert.equal(await card.evaluate(e=>e.open),false);
  }
  await page.locator('#latest-novaire-card').screenshot({path:`${out}/latest-${width}-${scale}x.png`});
  await page.locator('#weekly-asymmetric-ideas').scrollIntoViewIfNeeded();await page.screenshot({path:`${out}/peers-${width}-${scale}x.png`});
  await page.reload({waitUntil:'domcontentloaded'});await page.waitForTimeout(500);
  assert.deepEqual(await page.evaluate(ids=>ids.map(id=>document.getElementById(id).open),ids),ids.map(()=>false),'closed reload persistence');
  for(const id of ids)await page.locator('#'+id+'>summary').click();
  await page.waitForTimeout(100);await page.reload({waitUntil:'domcontentloaded'});await page.waitForTimeout(500);
  assert.deepEqual(await page.evaluate(ids=>ids.map(id=>document.getElementById(id).open),ids),ids.map(()=>true),'open reload persistence');
  const latest=page.locator('#latest-novaire-card');assert.equal(await latest.locator('.latest-novaire-item').count(),2,'both existing live social rows preserved (baseline has two, not six)');
  for(const summary of await latest.locator('.latest-novaire-item>summary').all())await summary.click();
  const expanded=await latest.evaluate(e=>({height:e.getBoundingClientRect().height,overflow:e.scrollHeight>e.clientHeight+1,rows:[...e.querySelectorAll('.latest-novaire-item')].map(x=>({open:x.open,height:x.getBoundingClientRect().height,visible:x.getBoundingClientRect().bottom<=e.getBoundingClientRect().bottom}))}));
  assert.equal(expanded.overflow,false);assert.ok(expanded.rows.every(x=>x.open&&x.visible));
  await latest.screenshot({path:`${out}/latest-expanded-${width}-${scale}x.png`});
  results.push({width,scale,initial,geometry,expanded});await context.close();
 }
 }finally{await browser.close();fs.writeFileSync(`${out}/results.json`,JSON.stringify(results,null,2));}
 console.log(JSON.stringify({ok:true,cases:results.length,results:results.map(x=>({width:x.width,scale:x.scale,heights:x.geometry.map(g=>g.height)})),out},null,2));
})().catch(e=>{console.error(e);process.exit(1)});
