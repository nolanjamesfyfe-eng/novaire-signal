import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import fs from 'node:fs';
import playwright from '/root/.hermes/cache/scratch/health-qa/node_modules/playwright-core/index.js';
const { chromium }=playwright;
const root=new URL('..',import.meta.url).pathname;
const out=process.env.HEALTH_PHYSIQUE_OUTPUT||'/root/.hermes/cache/scratch/output/health-physique';fs.mkdirSync(out,{recursive:true});
const tmp=root+'tests/.pw-physique-tmp';fs.mkdirSync(tmp,{recursive:true});process.env.TMPDIR=tmp;
const server=spawn('python3',['-m','http.server','4180','--bind','127.0.0.1'],{cwd:root,stdio:'ignore'});
for(let i=0;i<50;i++){try{const response=await fetch('http://127.0.0.1:4180/health/');if(response.ok)break}catch{}if(i===49)throw new Error('health QA server did not become ready on 127.0.0.1:4180');await new Promise(resolve=>setTimeout(resolve,100))}
let browser;
try{
 browser=await chromium.launch({headless:true,executablePath:'/snap/bin/chromium',args:['--no-sandbox']});
 const page=await browser.newPage({viewport:{width:1440,height:1000},deviceScaleFactor:1});
 const errors=[];page.on('pageerror',error=>errors.push(String(error)));
 await page.goto('http://127.0.0.1:4180/health/',{waitUntil:'domcontentloaded',timeout:120000});
 await page.waitForFunction(()=>window.__HEALTH_ATLAS__?.ready&&window.__HEALTH_BRAIN__?.ready,null,{timeout:120000});const deformation=await page.evaluate(()=>window.__HEALTH_PHYSIQUE_METRICS__);assert.ok(deformation.muscle.ratios.width<.93,`baseline anatomy must be regionally narrower than source (${deformation.muscle.ratios.width})`);assert.ok(deformation.muscle.ratios.depth<.9,`baseline anatomy must have reduced front-back depth (${deformation.muscle.ratios.depth})`);assert.ok(deformation.muscle.verticalEdit.headMaxDelta>20,'crown compression must be structurally meaningful');assert.equal(deformation.muscle.verticalEdit.nonHeadMaxDelta,0,'torso and limb vertical coordinates must remain unchanged by the cranial edit');await page.evaluate(()=>window.stop());
 await page.locator('.physique-toggle').click({noWaitAfter:true});
 assert.match(await page.locator('.physique-copy b').textContent(),/193 CM · 80 KG · LEAN ATHLETIC APPROXIMATION/);
 assert.equal(await page.locator('[data-physique="weight"]').inputValue(),'80');
 assert.equal(await page.locator('[data-physique="definition"]').inputValue(),'82');
 const span=points=>Math.max(...points.map(p=>p.x))-Math.min(...points.map(p=>p.x));
 const before=span(await page.evaluate(()=>window.__HEALTH_ATLAS__.projectAll('pectoralis')));
 await page.locator('[data-physique="weight"]').evaluate(input=>{input.value='110';input.dispatchEvent(new Event('input',{bubbles:true}))});
 const after=span(await page.evaluate(()=>window.__HEALTH_ATLAS__.projectAll('pectoralis')));
 assert.ok(after>before*1.08,`weight must visibly widen the frame (${before} -> ${after})`);
 assert.match(await page.locator('.physique-readout').textContent(),/110 KG · 82% DEFINITION/);
 await page.locator('[data-brain-part="frontal"]').click();assert.equal(await page.evaluate(()=>window.__HEALTH_BRAIN__.selected),'frontal');
 const stagePoint=await page.locator('.stage').evaluate(el=>{const r=el.getBoundingClientRect();return{x:r.left+8,y:r.bottom-8}});await page.mouse.click(stagePoint.x,stagePoint.y);assert.equal(await page.evaluate(()=>window.__HEALTH_BRAIN__.selected),null);
 await page.screenshot({path:out+'/desktop.png',fullPage:true});
 const mobile=await browser.newPage({viewport:{width:390,height:844},deviceScaleFactor:1});
 await mobile.goto('http://127.0.0.1:4180/health/',{waitUntil:'domcontentloaded',timeout:120000});await mobile.waitForFunction(()=>window.__HEALTH_ATLAS__?.ready,null,{timeout:120000});
 await mobile.locator('.physique-toggle').click({noWaitAfter:true});
 const geometry=await mobile.evaluate(()=>{const panel=document.querySelector('.physique-panel').getBoundingClientRect(),heading=document.querySelector('.intro').getBoundingClientRect(),viewport=document.querySelector('#viewport').getBoundingClientRect();return{overflow:document.documentElement.scrollWidth>innerWidth,panelRight:panel.right,panelLeft:panel.left,headingBottom:heading.bottom,viewportTop:viewport.top,figureBottom:viewport.bottom}});
 assert.equal(geometry.overflow,false);assert.ok(geometry.panelLeft>=0&&geometry.panelRight<=390);assert.ok(geometry.headingBottom<geometry.viewportTop+95);
 await mobile.screenshot({path:out+'/mobile.png',fullPage:true});
 assert.deepEqual(errors,[]);
 console.log(JSON.stringify({ok:true,baseline:'193cm/80kg/82%',dynamicFrame:{before,after},brainDismiss:true,mobile:geometry,screenshots:[out+'/desktop.png',out+'/mobile.png']}));
}finally{if(browser)await browser.close();server.kill('SIGTERM')}
