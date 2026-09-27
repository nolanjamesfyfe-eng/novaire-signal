import assert from 'node:assert/strict';
import { chromium } from 'playwright';
const base=process.env.BRAIN_QA_URL||'http://127.0.0.1:4177/tests/health-brain-fixture.html';
const browser=await chromium.launch({headless:true});
try{
  const page=await browser.newPage({viewport:{width:1440,height:1000},deviceScaleFactor:1});
  await page.goto(base,{waitUntil:'networkidle'});await page.waitForSelector('[data-brain-atlas][data-ready="true"]');
  const errors=[];page.on('pageerror',e=>errors.push(String(e)));
  const initial=await page.evaluate(()=>({ready:window.__HEALTH_BRAIN__.ready,distance:window.__HEALTH_BRAIN__.cameraDistance,selected:window.__HEALTH_BRAIN__.selected,level:window.__HEALTH_BRAIN__.level,labels:document.querySelectorAll('[data-brain-part]').length,copy:document.querySelector('.brain-atlas__signal p').textContent}));
  assert.equal(initial.ready,true);assert.equal(initial.labels,6);assert.equal(initial.selected,null);assert.equal(initial.level,null);assert.match(initial.copy,/not measured brain activity/i);assert.match(initial.copy,/not.*diagnosis/i);assert.match(initial.copy,/regional function/i);assert.match(initial.copy,/inferred neuroscience/i);
  await page.locator('[data-brain-part="cerebellum"]').click();assert.equal(await page.evaluate(()=>window.__HEALTH_BRAIN__.selected),'cerebellum');assert.equal(await page.locator('.brain-atlas__panel h3').textContent(),'Cerebellum');
  await page.locator('[data-brain-zoom="in"]').click();assert.ok(await page.evaluate(()=>window.__HEALTH_BRAIN__.cameraDistance)<initial.distance,'zoom in should reduce camera distance');
  const box=await page.locator('canvas').boundingBox();await page.mouse.move(box.x+box.width*.38,box.y+box.height*.5);await page.mouse.down();await page.mouse.move(box.x+box.width*.64,box.y+box.height*.45,{steps:12});await page.mouse.up();await page.waitForTimeout(180);const rotated=await page.screenshot({path:'tests/health-brain-desktop.png',fullPage:true});assert.ok(rotated.length>10000);
  await page.evaluate(()=>document.dispatchEvent(new CustomEvent('health:checkin',{detail:{answers:{energy:9,focus:8,sleep:8}}})));await page.waitForTimeout(100);assert.ok(Math.abs((await page.evaluate(()=>window.__HEALTH_BRAIN__.level))-0.9)<.001);assert.match(await page.locator('[data-brain-signal]').textContent(),/90% · SELF-REPORTED/);
  await page.evaluate(()=>document.dispatchEvent(new CustomEvent('health:checkin',{detail:null})));assert.equal(await page.evaluate(()=>window.__HEALTH_BRAIN__.level),null);
  assert.deepEqual(errors,[]);
  const mobile=await browser.newPage({viewport:{width:390,height:844},deviceScaleFactor:1});await mobile.goto(base,{waitUntil:'networkidle'});await mobile.waitForSelector('[data-brain-atlas][data-ready="true"]');const collision=await mobile.evaluate(()=>{const deck=document.querySelector('.brain-atlas__deck').getBoundingClientRect(),panel=document.querySelector('.brain-atlas__panel').getBoundingClientRect(),vp=document.querySelector('.brain-atlas__viewport').getBoundingClientRect();return{overflow:document.documentElement.scrollWidth>innerWidth,panelOverlap:panel.top<vp.bottom-1,deckHeight:deck.height}});assert.equal(collision.overflow,false);assert.equal(collision.panelOverlap,false);await mobile.screenshot({path:'tests/health-brain-mobile.png',fullPage:true});
  console.log(JSON.stringify({ok:true,rotation:true,selection:true,zoom:true,checkinResponse:true,mobile:collision,screenshots:['tests/health-brain-desktop.png','tests/health-brain-mobile.png']}));
}finally{await browser.close()}
