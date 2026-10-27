import playwright from '/root/.hermes/cache/scratch/health-qa/node_modules/playwright-core/index.js';
import {spawn} from 'node:child_process';
import {strict as assert} from 'node:assert';
import fs from 'node:fs';
const root=new URL('..',import.meta.url).pathname;
const evidence=process.env.HEALTH_INLINE_EVIDENCE||'/root/.hermes/cache/scratch/health-inline';fs.mkdirSync(evidence,{recursive:true});
const live=process.env.HEALTH_INLINE_URL;
const server=live?null:spawn('python3',['-u','-m','http.server','4198','--bind','127.0.0.1'],{cwd:root});
if(server)await new Promise((ok,no)=>{server.stdout.on('data',b=>{if(String(b).includes('Serving HTTP'))ok()});server.on('error',no)});
const browser=await playwright.chromium.launch({headless:true,executablePath:'/root/.cache/ms-playwright/chromium-1248/chrome-linux64/chrome',args:['--no-sandbox']});
try{for(const width of [390,1440]){
 const context=await browser.newContext({viewport:{width,height:900}}),page=await context.newPage();page.setDefaultTimeout(8000);
 // Only the API fixture mode intercepts health data. Live smoke never sends a PIN or PUT.
 let auth=false,fail=false,expire=false,storeFail=false,conflict=false,revision=9,entries=[],puts=[];
 await page.route(/.*\/(atlas|brain-atlas|injury-journal)\.js.*/,r=>r.fulfill({contentType:'application/javascript',body:''}));
 if(!process.env.HEALTH_INLINE_REAL){
 await page.route('**/api/health-auth',r=>{auth=!fail;return r.fulfill({status:fail?401:200,json:fail?{error:'Incorrect PIN.'}:{ok:true}})});
 await page.route('**/api/health-record',r=>r.fulfill({status:auth?200:401,json:auth?{record:{label:'Fixture'}}:{error:'Unauthorized'}}));
 await page.route('**/api/health-checkins',r=>{if(!auth||expire)return r.fulfill({status:401,json:{error:'Authentication required'}});if(storeFail)return r.fulfill({status:503,json:{error:'Private check-in storage is temporarily unavailable.'}});if(r.request().method()==='PUT'){const b=r.request().postDataJSON();puts.push(b);if(conflict)return r.fulfill({status:409,json:{error:'Conflict'}});assert.equal(b.revision,revision);const a=b.entry.answers;entries=[{...b.entry,calculationVersion:3,scaleMax:10,score:Math.round((a.energy+a.focus+10-a.stress+a.calm+a.happiness)*2)}];revision++;}return r.fulfill({json:{revision,entries}})});
 }
 await page.goto(live||'http://127.0.0.1:4198/health/',{waitUntil:'domcontentloaded'});
 await page.locator('.energy-checkin-open').click();
 assert.equal(await page.locator('.energy-pin').isVisible(),true,'PIN must be inline before the first save');
 assert.equal(await page.locator('.energy-form details[open]').count(),0,'optional details start collapsed');
 const energy=page.locator('[name=energy]');await energy.focus();await energy.press('End');await energy.press('ArrowLeft');assert.equal(await energy.inputValue(),'9');
 await page.locator('.energy-save').click();assert.equal(await page.locator('.energy-dialog').evaluate(x=>x.open),true);assert.equal(await page.locator('.energy-pin').evaluate(x=>x===document.activeElement),true);
 await page.screenshot({path:`${evidence}/inline-${width}.png`});
 if(process.env.HEALTH_INLINE_REAL){console.log(`PASS live anonymous ${width}: inline PIN, native slider, one save, no detour; no writes`);await context.close();continue;}
 await page.locator('.energy-foundations summary').click();await page.locator('[name=foodNotes]').fill('Isolated draft');await page.locator('.energy-foundations summary').click();
 fail=true;await page.locator('.energy-pin').fill('00000');await page.locator('.energy-save').click();await page.waitForFunction(()=>document.querySelector('.energy-feedback').textContent.includes('Incorrect PIN'));assert.equal(puts.length,0);assert.equal(await energy.inputValue(),'9');
 fail=false;storeFail=true;await page.locator('.energy-pin').fill('00000');await page.locator('.energy-save').click();await page.waitForFunction(()=>document.querySelector('.energy-feedback').textContent.includes('storage'));assert.equal(puts.length,0);assert.equal(await energy.inputValue(),'9');
 storeFail=false;await page.locator('.energy-save').click();await page.waitForFunction(()=>document.querySelector('.energy-feedback').textContent.includes('Saved privately'));assert.equal(puts.length,1);assert.equal(puts[0].entry.foundations.foodNotes,'Isolated draft');
 await page.waitForFunction(()=>!document.querySelector('.energy-dialog').open);await page.reload({waitUntil:'domcontentloaded'});await page.waitForFunction(()=>document.querySelector('.energy-history-count').textContent.includes('1 entry'));
 await page.locator('.energy-checkin-open').click();assert.equal(await energy.inputValue(),'9');assert.equal(await page.locator('.energy-pin').isVisible(),false,'valid session restores without another PIN');
 page.on('dialog',d=>d.accept());await energy.press('Home');await energy.press('ArrowRight');expire=true;await page.locator('.energy-save').click();await page.waitForFunction(()=>!document.querySelector('.energy-auth').hidden);assert.equal(await energy.inputValue(),'1');expire=false;
 await page.locator('.energy-pin').fill('00000');conflict=true;await page.locator('.energy-save').click();await page.waitForFunction(()=>document.querySelector('.energy-feedback').textContent.includes('another device'));assert.equal(await energy.inputValue(),'1');
 conflict=false;await page.locator('.energy-save').click();await page.waitForFunction(()=>document.querySelector('.energy-feedback').textContent.includes('Saved privately'));assert.equal(puts.at(-1).confirmOverwrite,true);
 await page.waitForFunction(()=>!document.querySelector('.energy-dialog').open);await page.locator('.health-private__logout').click();await page.locator('.energy-checkin-open').click();assert.equal(await energy.inputValue(),'5');await page.keyboard.press('Escape');
 console.log(`PASS fixture ${width}: inline auth, wrong PIN, storage failure/retry, draft, single save, restore session, expired session, CAS conflict, explicit lock`);await context.close();
}}finally{await browser.close();server?.kill()}
