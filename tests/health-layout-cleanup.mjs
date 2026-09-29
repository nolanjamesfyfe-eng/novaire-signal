import assert from 'node:assert/strict';
import {spawn} from 'node:child_process';
import fs from 'node:fs';
import playwright from '/root/.hermes/cache/scratch/health-qa/node_modules/playwright-core/index.js';
const root=new URL('..',import.meta.url).pathname,out='/root/.hermes/cache/scratch/health-layout-cleanup';fs.mkdirSync(out,{recursive:true});
const server=spawn('python3',['-m','http.server','4242','--bind','127.0.0.1'],{cwd:root,stdio:'ignore'});
let browser;
try{
 for(let i=0;i<40;i++){try{if((await fetch('http://127.0.0.1:4242/health/')).ok)break}catch{}await new Promise(r=>setTimeout(r,100))}
 browser=await playwright.chromium.launch({headless:true,executablePath:'/opt/google/chrome/chrome',args:['--no-sandbox']});
 for(const width of [390,360,1440]){
 const page=await browser.newPage({viewport:{width,height:1000},deviceScaleFactor:1});
 await page.goto(process.env.HEALTH_LAYOUT_URL||'http://127.0.0.1:4242/health/',{waitUntil:'domcontentloaded'});
 await page.waitForFunction(()=>window.__HEALTH_ATLAS__?.ready,{timeout:120000});
 assert.equal(await page.locator('.intro .eyebrow').count(),0);
 assert.equal(await page.locator('#atlas-title').count(),1);
 const metrics=await page.evaluate(()=>{const rect=s=>{const r=document.querySelector(s).getBoundingClientRect();return {top:r.top,bottom:r.bottom,left:r.left,right:r.right}};return {stage:rect('.stage'),preview:rect('.physique-control'),layers:rect('.layer-controls'),views:rect('.view-controls')}});
 assert.ok(metrics.preview.top>=metrics.stage.bottom,'preview below model, not overlaid');
 if(width<761)assert.ok(metrics.layers.bottom<=metrics.views.top,'layer and view controls separate');
 await page.screenshot({path:`${out}/${width}-top.png`,timeout:60000});
 await page.locator('.physique-toggle').click();
 assert.equal(await page.locator('.physique-toggle').getAttribute('aria-expanded'),'true');
 assert.ok(await page.locator('.physique-panel').isVisible());
 const expanded=await page.locator('.physique-panel').boundingBox();assert.ok(expanded.x>=0&&expanded.x+expanded.width<=width,'expanded preview fits viewport');
 await page.screenshot({path:`${out}/${width}-preview.png`,timeout:60000});
 console.log('PASS',width,JSON.stringify(metrics));await page.close();
 }
}finally{await browser?.close();server.kill()}
