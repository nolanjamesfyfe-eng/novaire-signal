import assert from 'node:assert/strict';
import {spawn} from 'node:child_process';
import fs from 'node:fs';
import playwright from '/root/.hermes/cache/scratch/health-qa/node_modules/playwright-core/index.js';
const {chromium}=playwright;
const root=process.env.HEALTH_ROOT||new URL('..',import.meta.url).pathname;
const out=process.env.HEALTH_ARMS_OUTPUT||'/root/.hermes/cache/scratch/output/health-lean-arms';
const port=process.env.HEALTH_PORT||'4187';
process.env.TMPDIR=process.env.HEALTH_TMPDIR||root+'/tests/.pw-lean-arms-tmp';fs.mkdirSync(process.env.TMPDIR,{recursive:true});
fs.mkdirSync(out,{recursive:true});
const server=spawn('python3',['-m','http.server',port,'--bind','127.0.0.1'],{cwd:root,stdio:'ignore'});
let browser;
for(let i=0;i<80;i++){try{if((await fetch(`http://127.0.0.1:${port}/health/`)).ok)break}catch{}if(i===79)throw new Error('local health server unavailable');await new Promise(r=>setTimeout(r,100))}
try{
 browser=await chromium.launch({headless:true,executablePath:'/snap/bin/chromium',args:['--no-sandbox']});
 const results=[];
 for(const [device,viewport] of Object.entries({desktop:{width:1440,height:1000},mobile:{width:390,height:844}})){
  const page=await browser.newPage({viewport,deviceScaleFactor:1});const errors=[];page.on('pageerror',e=>errors.push(String(e)));
  await page.goto(`http://127.0.0.1:${port}/health/`,{waitUntil:'domcontentloaded',timeout:120000});await page.waitForFunction(()=>window.__HEALTH_ATLAS__?.ready,null,{timeout:120000});
  for(const view of ['front','right','back','left']){
   await page.evaluate(view=>document.querySelector(`[data-view="${view}"]`).click(),view);await page.waitForTimeout(650);
   const viewportBox=await page.locator('#viewport').boundingBox();assert.ok(viewportBox);
   await page.screenshot({path:`${out}/${device}-${view}-clear.png`,clip:viewportBox});
   if(view==='right'){
    await page.locator('.muscle-item[data-key="upper-arm-surface"]').click();await page.waitForTimeout(250);
    assert.equal(await page.evaluate(()=>window.__HEALTH_ATLAS__.selected),'upper-arm-surface');
    await page.screenshot({path:`${out}/${device}-${view}-upper-arm-selected.png`,clip:viewportBox});
   }
  }
  assert.deepEqual(errors,[]);results.push({device,selected:await page.evaluate(()=>window.__HEALTH_ATLAS__.selected)});await page.close();
 }
 console.log(JSON.stringify({ok:true,root,out,results}));
}finally{if(browser)await browser.close();server.kill('SIGTERM')}
