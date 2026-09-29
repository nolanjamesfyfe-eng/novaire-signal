import assert from 'node:assert/strict';
import fs from 'node:fs';
import {spawn} from 'node:child_process';
import playwright from '/root/.hermes/cache/scratch/health-qa/node_modules/playwright-core/index.js';
const root=new URL('..',import.meta.url).pathname;
const out=process.env.HEALTH_OPTION1_OUTPUT||'/root/.hermes/cache/scratch/output/health-option1-final';
fs.mkdirSync(out,{recursive:true});
process.env.TMPDIR=root+'tests/.pw-option1-tmp';fs.mkdirSync(process.env.TMPDIR,{recursive:true});
const server=spawn('python3',['-m','http.server','4191','--bind','127.0.0.1'],{cwd:root,stdio:'ignore'});
let browser;
for(let i=0;i<60;i++){try{if((await fetch('http://127.0.0.1:4191/health/')).ok)break}catch{}await new Promise(r=>setTimeout(r,100))}
async function ready(page){await page.goto('http://127.0.0.1:4191/health/',{waitUntil:'domcontentloaded',timeout:120000});await page.waitForFunction(()=>window.__HEALTH_ATLAS__?.ready===true,null,{timeout:120000});await page.addStyleTag({content:'.intro,.axis-label,.viewer-kicker{display:none!important}'});await page.waitForTimeout(400)}
async function shot(page,path){const clip=await page.locator('#atlas-canvas').boundingBox();await page.screenshot({path,clip,animations:'disabled'})}
try{
 browser=await playwright.chromium.launch({headless:true,executablePath:'/snap/bin/chromium',args:['--no-sandbox']});
 const desktop=await browser.newPage({viewport:{width:1600,height:1200},deviceScaleFactor:1});await ready(desktop);const errors=[];desktop.on('pageerror',e=>errors.push(String(e)));
 const metrics=await desktop.evaluate(()=>window.__HEALTH_PHYSIQUE_METRICS__);assert.equal(metrics.muscle.profile,'option-1-balanced-natural-lean');
 for(const view of ['front','right','back']){await desktop.evaluate(v=>window.__HEALTH_ATLAS__.view(v),view);await desktop.waitForTimeout(650);await shot(desktop,`${out}/desktop-muscle-${view}-whole.png`)}
 const head=await desktop.evaluate(()=>window.__HEALTH_ATLAS__.muscleHead);assert.ok(head.visible&&head.triangles>30000,'muscle head is visible before changing layers');
 for(const view of ['front','right']){assert.equal(await desktop.evaluate(v=>window.__HEALTH_ATLAS__.focusHead(v),view),true);await desktop.waitForTimeout(250);await shot(desktop,`${out}/desktop-head-${view}-close.png`)}
 await desktop.evaluate(()=>{document.querySelector('[data-layer="skin"]').click();window.__HEALTH_ATLAS__.view('front')});await desktop.waitForTimeout(650);await shot(desktop,`${out}/desktop-skin-front-whole.png`);
 const mobile=await browser.newPage({viewport:{width:390,height:844},deviceScaleFactor:1});await ready(mobile);await shot(mobile,`${out}/mobile-muscle-front-whole.png`);await mobile.evaluate(()=>window.__HEALTH_ATLAS__.view('back'));await mobile.waitForTimeout(650);await shot(mobile,`${out}/mobile-muscle-back-whole.png`);
 const acceptance=await desktop.evaluate(()=>({head:window.__HEALTH_ATLAS__.muscleHead,ledger:window.__HEALTH_ATLAS__.acceptanceLedger,metrics:window.__HEALTH_PHYSIQUE_METRICS__}));assert.ok(acceptance.head.triangles>30000);assert.equal(acceptance.ledger.outlineObjects,0);assert.deepEqual(errors,[]);fs.writeFileSync(`${out}/measurements.json`,JSON.stringify(acceptance,null,2));console.log(JSON.stringify(acceptance,null,2));console.log(`PASS option1 visual QA; screenshots=${out}`);
}finally{if(browser)await browser.close();server.kill('SIGTERM')}
