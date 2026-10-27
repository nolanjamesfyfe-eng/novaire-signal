import playwright from '/root/.hermes/cache/scratch/health-qa/node_modules/playwright-core/index.js';
import {spawn} from 'node:child_process';
import {strict as assert} from 'node:assert';
import fs from 'node:fs';
const root=new URL('..',import.meta.url).pathname;
const evidence=process.env.HEALTH_UNLOCK_EVIDENCE||'/root/.hermes/cache/scratch/health-unlock';
fs.mkdirSync(evidence,{recursive:true});
const server=process.env.HEALTH_UNLOCK_URL?null:spawn('python3',['-u','-m','http.server','4197','--bind','127.0.0.1'],{cwd:root});
if(server)await new Promise((resolve,reject)=>{server.stdout.on('data',b=>{if(String(b).includes('Serving HTTP'))resolve()});server.on('error',reject);server.on('exit',()=>reject(new Error('server exited')))});
const browser=await playwright.chromium.launch({headless:true,executablePath:process.env.CHROMIUM_PATH||'/root/.cache/ms-playwright/chromium-1248/chrome-linux64/chrome',args:['--no-sandbox']});
try{
for(const width of [390,1440]){
 const context=await browser.newContext({viewport:{width,height:900},serviceWorkers:'block'}), page=await context.newPage();
 let authenticated=false,failAuth=false,expire=false,conflict=false,revision=9,entries=[],puts=[];
 const errors=[];page.on('pageerror',e=>errors.push(String(e)));
 // Isolate this DOM flow from software-rendered WebGL, not from the private UI.
 await page.route(/.*\/(atlas|brain-atlas|injury-journal)\.js.*/,r=>r.fulfill({contentType:'application/javascript',body:''}));
 await page.route('**/api/health-auth',r=>{authenticated=!failAuth;return r.fulfill({status:failAuth?401:200,json:failAuth?{error:'Incorrect PIN.'}:{ok:true}})});
 await page.route('**/api/health-record',r=>r.fulfill({status:authenticated?200:401,json:authenticated?{record:{label:'Isolated test fixture'}}:{error:'Unauthorized'}}));
 await page.route('**/api/health-checkins',r=>{
  if(!authenticated||expire)return r.fulfill({status:401,json:{error:'Unauthorized'}});
  if(r.request().method()==='PUT'){
   const body=r.request().postDataJSON();puts.push(body);
   if(conflict)return r.fulfill({status:409,json:{error:'Conflict'}});
   assert.equal(body.revision,revision);const a=body.entry.answers;
   const entry={...body.entry,schemaVersion:3,scaleMax:10,score:Math.round((a.energy+a.focus+10-a.stress+a.calm+a.happiness)*2)};
   entries=[entry];revision++;
  }
  return r.fulfill({json:{revision,entries}});
 });
 await page.goto(process.env.HEALTH_UNLOCK_URL||'http://127.0.0.1:4197/health/',{waitUntil:'domcontentloaded'});
 await page.locator('.energy-checkin-open').click();
 const energy=page.locator('[name=energy]');await energy.focus();await energy.press('End');await energy.press('ArrowLeft');assert.equal(await energy.inputValue(),'9');
 await page.locator('[name=foodNotes]').fill('Isolated draft survives unlock');
 const date=await page.locator('[name=date]').inputValue();
 await page.locator('.energy-save').click();assert.equal(puts.length,0);
 await page.locator('.energy-unlock').click();
 await page.locator('#health-private-pin').fill('00000');await page.locator('.health-private__form button').click();
 await page.waitForFunction(()=>document.querySelector('.energy-dialog').open,{},{timeout:4000});
 assert.equal(await energy.inputValue(),'9');assert.equal(await page.locator('[name=foodNotes]').inputValue(),'Isolated draft survives unlock');assert.equal(await page.locator('[name=date]').inputValue(),date);
 assert.equal(puts.length,0,'unlock must not implicitly save');
 await page.locator('.energy-save').click();await page.waitForFunction(()=>document.querySelector('.energy-feedback').textContent.includes('Saved privately'));
 assert.equal(puts.length,1);assert.equal(puts[0].revision,9);
 await page.waitForFunction(()=>!document.querySelector('.energy-dialog').open);
 await page.locator('.energy-checkin-open').click();await energy.focus();await energy.press('Home');await energy.press('ArrowRight');assert.equal(await energy.inputValue(),'1');
 page.on('dialog',d=>d.accept());expire=true;await page.locator('.energy-save').click();await page.locator('.energy-unlock').click();
 failAuth=true;await page.locator('#health-private-pin').fill('00000');await page.locator('.health-private__form button').click();await page.waitForFunction(()=>document.querySelector('.health-private__status').textContent.includes('Incorrect PIN'));
 failAuth=false;expire=false;await page.locator('#health-private-pin').fill('00000');await page.locator('.health-private__form button').click();await page.waitForFunction(()=>document.querySelector('.energy-dialog').open);
 assert.equal(await energy.inputValue(),'1','failed PIN retry must preserve suspended draft');
 conflict=true;await page.locator('.energy-save').click();await page.waitForFunction(()=>document.querySelector('.energy-feedback').textContent.includes('another device'));assert.equal(await energy.inputValue(),'1');
 conflict=false;await page.locator('.energy-save').click();await page.waitForFunction(()=>document.querySelector('.energy-feedback').textContent.includes('Saved privately'));assert.equal(puts.at(-1).revision,10);assert.equal(puts.at(-1).confirmOverwrite,true);
 await page.waitForFunction(()=>!document.querySelector('.energy-dialog').open);await page.reload({waitUntil:'domcontentloaded'});
 await page.locator('#health-private-pin').fill('00000');await page.locator('.health-private__form button').click();await page.waitForFunction(()=>document.querySelector('.energy-history-count').textContent.includes('1 entry'));
 await page.locator('.energy-checkin-open').click();assert.equal(await energy.inputValue(),'1','fixture server edit survives reload');
 await page.locator('.energy-save').scrollIntoViewIfNeeded();await page.screenshot({path:`${evidence}/unlock-${width}.png`});assert.deepEqual(errors,[]);
 await page.locator('.energy-close').click();await page.locator('.health-private__logout').click();await page.waitForFunction(()=>document.querySelector('.energy-history-count').textContent.includes('0 entries'));
 await page.locator('.energy-checkin-open').click();assert.equal(await energy.inputValue(),'5','explicit lock must clear private form state');await page.locator('[name=foodNotes]').fill('Discard this draft');await page.locator('.energy-save').click();await page.locator('.energy-unlock').click();
 await page.locator('.energy-checkin-open').click();assert.equal(await page.locator('[name=foodNotes]').inputValue(),'Discard this draft');await page.keyboard.press('Escape');
 await page.locator('#health-private-pin').fill('00000');await page.locator('.health-private__form button').click();await page.waitForFunction(()=>document.querySelector('.energy-history-count').textContent.includes('1 entry'));assert.equal(await page.locator('.energy-dialog').evaluate(d=>d.open),false,'cancel must stop automatic draft resumption');
 await context.close();console.log(`PASS ${width}: native slider, blocked Update, unlock return/draft, expired session, wrong PIN retry, CAS conflict, save/edit/reload (isolated API fixtures)`);
}
}finally{await browser.close();server?.kill()}
