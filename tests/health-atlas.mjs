import playwright from '/root/.hermes/cache/scratch/health-qa/node_modules/playwright-core/index.js';
const { chromium } = playwright;
import { spawn } from 'node:child_process';
import { strict as assert } from 'node:assert';
import fs from 'node:fs';
const root=new URL('..',import.meta.url).pathname;
assert.ok(fs.statSync(root+'health/models/bodyparts3d.glb').size<3_000_000,'compressed anatomy bundle must stay below 3 MB');
assert.equal(fs.readdirSync(root+'health/models').filter(x=>x.endsWith('.obj')).length,0,'legacy OBJ payloads must not ship');
const tmp=root+'tests/.pw-tmp';fs.mkdirSync(tmp,{recursive:true});process.env.TMPDIR=tmp;
const server=spawn('python3',['-m','http.server','4178','--bind','127.0.0.1'],{cwd:root,stdio:'ignore'});
await new Promise(r=>setTimeout(r,700));
let browser;
const near=(a,b,e=.18)=>Math.abs(a-b)<e;
try{
 browser=await chromium.launch({headless:true,executablePath:'/snap/bin/chromium',args:['--no-sandbox']});
 const page=await browser.newPage({viewport:{width:1440,height:1000},deviceScaleFactor:1});
 const errors=[];page.on('pageerror',e=>errors.push(String(e)));page.on('console',m=>{if(m.type()==='error'&&!m.text().includes('Failed to load resource'))errors.push(m.text())});
 await page.goto('http://127.0.0.1:4178/health/',{waitUntil:'domcontentloaded',timeout:120000});
 await page.waitForFunction(()=>window.__HEALTH_ATLAS__?.ready===true,null,{timeout:120000});
 const state=await page.evaluate(()=>({muscles:window.__HEALTH_ATLAS__.muscleCount,parts:window.__HEALTH_ATLAS__.parts,ready:document.documentElement.dataset.atlasReady}));
 assert.equal(state.muscles,14);assert.ok(state.parts>=48);assert.equal(state.ready,'true');
 // A genuine pointer event goes through canvas hit testing and the Three.js raycaster.
 const pec=await page.evaluate(()=>window.__HEALTH_ATLAS__.project('pectoralis'));assert.ok(pec);
 await page.mouse.click(pec.x,pec.y);await page.waitForFunction(()=>window.__HEALTH_ATLAS__.selected==='pectoralis');
 assert.equal(await page.locator('#muscle-name').textContent(),'Pectoralis major');
 // Orbit drag must move the camera and must never silently enable auto-rotation.
 const box=await page.locator('#atlas-canvas').boundingBox(),before=await page.evaluate(()=>window.__HEALTH_ATLAS__.state);
 await page.mouse.move(box.x+box.width*.55,box.y+box.height*.48);await page.mouse.down();await page.mouse.move(box.x+box.width*.74,box.y+box.height*.54,{steps:12});await page.mouse.up();await page.waitForTimeout(250);
 const dragged=await page.evaluate(()=>window.__HEALTH_ATLAS__.state);assert.notDeepEqual(dragged.camera,before.camera);assert.equal(dragged.autoRotate,false);assert.equal(dragged.controlsAutoRotate,false);
 // Front/back are absolute camera views even after arbitrary orbit dragging.
 await page.locator('[data-view="back"]').click();await page.waitForTimeout(650);let view=await page.evaluate(()=>window.__HEALTH_ATLAS__.state);assert.ok(view.camera[2]<-7);assert.ok(near(view.camera[0],0));
 const backPoints=await page.evaluate(()=>window.__HEALTH_ATLAS__.projectAll('triceps'));for(const p of backPoints){await page.mouse.click(p.x,p.y);if(await page.evaluate(()=>window.__HEALTH_ATLAS__.selected==='triceps'))break}assert.equal(await page.evaluate(()=>window.__HEALTH_ATLAS__.selected),'triceps');
 await page.locator('[data-view="front"]').click();await page.waitForTimeout(650);view=await page.evaluate(()=>window.__HEALTH_ATLAS__.state);assert.ok(view.camera[2]>7);assert.ok(near(view.camera[0],0));
 // Zoom, focus and reset are camera-relative and survive any prior orbit.
 const d0=await page.evaluate(()=>{const s=window.__HEALTH_ATLAS__.state;return Math.hypot(...s.camera.map((v,i)=>v-s.target[i]))});await page.locator('#zoom-in').click();const d1=await page.evaluate(()=>{const s=window.__HEALTH_ATLAS__.state;return Math.hypot(...s.camera.map((v,i)=>v-s.target[i]))});assert.ok(d1<d0);
 const preFocus=await page.evaluate(()=>window.__HEALTH_ATLAS__.state);await page.locator('#focus-button').click();await page.waitForTimeout(650);let focused=await page.evaluate(()=>window.__HEALTH_ATLAS__.state);assert.notDeepEqual(focused.camera,preFocus.camera);
 await page.locator('[data-view="reset"]').click();await page.waitForTimeout(650);view=await page.evaluate(()=>window.__HEALTH_ATLAS__.state);assert.ok(near(view.camera[2],22));assert.ok(Math.hypot(...view.target)<.05);
 await page.locator('#search').fill('calf');assert.equal(await page.locator('.muscle-item:not([hidden])').count(),2);
 // The semantic directory is fully keyboard operable and drives a visibly selected structure.
 await page.locator('.muscle-item:not([hidden])').first().focus();await page.keyboard.press('Enter');assert.equal(await page.evaluate(()=>window.__HEALTH_ATLAS__.selected),'gastrocnemius');
 await page.screenshot({path:root+'tests/health-atlas-desktop.png',fullPage:true});
 const mobile=await browser.newPage({viewport:{width:390,height:844},deviceScaleFactor:1});await mobile.goto('http://127.0.0.1:4178/health/',{waitUntil:'domcontentloaded',timeout:120000});await mobile.waitForFunction(()=>window.__HEALTH_ATLAS__?.ready,null,{timeout:120000});const overlap=await mobile.evaluate(()=>{const h=document.querySelector('.intro').getBoundingClientRect(),v=document.querySelector('#viewport').getBoundingClientRect();return h.bottom>v.top+95});assert.equal(overlap,false);await mobile.screenshot({path:root+'tests/health-atlas-mobile.png',fullPage:true});
 // Force WebGL creation failure: directory/search remain usable and no body reference is touched.
 const fallback=await browser.newPage();await fallback.addInitScript(()=>{HTMLCanvasElement.prototype.getContext=()=>null});const fallbackErrors=[];fallback.on('pageerror',e=>fallbackErrors.push(String(e)));await fallback.goto('http://127.0.0.1:4178/health/',{waitUntil:'domcontentloaded'});await fallback.waitForTimeout(500);assert.equal(await fallback.locator('#webgl-fallback').isVisible(),true);await fallback.locator('#search').fill('deltoid');assert.equal(await fallback.locator('.muscle-item:not([hidden])').count(),1);assert.equal(fallbackErrors.filter(e=>/body is not defined|undefined body/i.test(e)).length,0);
 assert.equal(errors.length,0,errors.join('\n'));
 console.log(`PASS health atlas: ${state.muscles} medically named groups / ${state.parts} BodyParts3D meshes; real pointer raycast; orbit drag; absolute front/back; zoom/focus/reset; WebGL fallback; desktop/mobile screenshots; 0 browser errors`);
}finally{if(browser)await browser.close();server.kill('SIGTERM')}
