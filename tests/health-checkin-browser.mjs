import playwright from '/root/.hermes/cache/scratch/health-qa/node_modules/playwright-core/index.js';
import {spawn} from 'node:child_process';
import {strict as assert} from 'node:assert';
import fs from 'node:fs';
const root=new URL('..',import.meta.url).pathname,tmp=root+'tests/.pw-checkin';
fs.mkdirSync(tmp,{recursive:true});process.env.TMPDIR=tmp;
const server=spawn('python3',['-m','http.server','4181','--bind','127.0.0.1'],{cwd:root,stdio:'ignore'});
await new Promise(r=>setTimeout(r,700));let browser;
try{
  browser=await playwright.chromium.launch({headless:true,executablePath:'/snap/bin/chromium',args:['--no-sandbox']});
  const page=await browser.newPage({viewport:{width:390,height:844}}),errors=[];page.on('pageerror',e=>errors.push(String(e)));
  let releaseLoad;const loadGate=new Promise(r=>{releaseLoad=r});
  await page.route('**/api/health-checkins',async route=>{await loadGate;await route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({revision:9,entries:[{date:'2026-09-20',score:100,scaleMax:10,answers:{energy:10,focus:10,stress:0,calm:10,happiness:10},foundations:{sleepHours:8}}]})})});
  await page.goto('http://127.0.0.1:4181/health/',{waitUntil:'domcontentloaded'});
  const today=await page.evaluate(()=>HealthCheckinModel.bangkokDate());
  await page.evaluate(({today})=>{localStorage.setItem('novaire-health-energy-checkins-v1',JSON.stringify([
    {date:today,schemaVersion:2,scaleMax:10,score:61,answers:{energy:6,focus:6,stress:4,calm:6,happiness:6},foundations:{sleepHours:7,fluidsLiters:0,anki:'no'}},
    {date:'<img src=x onerror=window.__xss=1>',score:'<svg/onload=window.__xss=2>',answers:{energy:5,focus:5,stress:5,calm:5,happiness:5}}
  ]));location.reload()},{today});
  await page.waitForLoadState('domcontentloaded');
  await page.waitForFunction(()=>document.querySelector('.energy-history-count')?.textContent.includes('1 entry'));
  assert.equal(await page.locator('.energy-history-list button').count(),1,'invalid legacy entry must not render');
  assert.equal(await page.evaluate(()=>window.__xss),undefined);
  await page.locator('[data-view="week"]').evaluate(el=>el.click());
  assert.equal(await page.locator('.energy-percent').textContent(),'8.7%');
  assert.match(await page.locator('.energy-average').textContent(),/61.0%/);
  assert.match(await page.locator('.energy-coverage').textContent(),/1 of 7/);
  const fills=await page.locator('.energy-segment').evaluateAll(xs=>xs.map(x=>x.style.getPropertyValue('--fill')));
  assert.equal(fills[0],'87.14285714285714%');assert.equal(fills.slice(1).every(x=>x==='0%'),true);
  await page.locator('[data-view="day"]').evaluate(el=>el.click());
  const dayFills=await page.locator('.energy-segment').evaluateAll(xs=>xs.map(x=>x.style.getPropertyValue('--fill')));
  assert.equal(dayFills.slice(0,6).every(x=>x==='100%'),true,'full battery segments must clamp to 100%');assert.equal(dayFills[6],'10%');
  assert.match(await page.locator('.energy-metrics').textContent(),/Sleep[\s\S]*7.0h[\s\S]*1 \/ 1 days answered/);
  assert.match(await page.locator('.energy-metrics').textContent(),/Fluids[\s\S]*0.0L/,'zero must remain distinct from unknown');
  await page.locator('.energy-checkin-open').click();
  assert.equal(await page.locator('[name="energy"]').inputValue(),'6');
  await page.locator('[name="date"]').fill('2026-09-01');await page.locator('[name="date"]').dispatchEvent('change');
  assert.equal(await page.locator('[name="energy"]').inputValue(),'5','backfill date loads blank defaults');
  assert.equal(await page.locator('[name="sleepHours"]').inputValue(),'');
  await page.evaluate(()=>window.dispatchEvent(new CustomEvent('health:record-ready')));
  await page.evaluate(()=>window.dispatchEvent(new CustomEvent('health:record-cleared')));
  releaseLoad();await page.waitForTimeout(150);
  assert.equal(await page.locator('.energy-dialog').isVisible(),false,'logout closes private modal');
  assert.equal(await page.locator('.energy-history-list button').count(),0,'late load cannot restore private entries');
  assert.match(await page.locator('.energy-sync').textContent(),/Locked/);
  await page.screenshot({path:root+'tests/health-checkin-mobile.png',fullPage:true});
  assert.equal(errors.length,0,errors.join('\n'));
  console.log('PASS mobile UI: validated legacy input, XSS-safe history, segment clamp, trends/coverage, date reload, logout race');
}finally{if(browser)await browser.close();server.kill('SIGTERM')}
