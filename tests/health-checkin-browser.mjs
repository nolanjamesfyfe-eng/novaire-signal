import playwright from '/root/.hermes/cache/scratch/health-qa/node_modules/playwright-core/index.js';
import {spawn} from 'node:child_process';
import {strict as assert} from 'node:assert';
import fs from 'node:fs';
const root=new URL('..',import.meta.url).pathname,tmp=root+'tests/.pw-checkin',evidence=process.env.HEALTH_CHECKIN_EVIDENCE||root+'tests/evidence';
fs.mkdirSync(tmp,{recursive:true});fs.mkdirSync(evidence,{recursive:true});process.env.TMPDIR=tmp;
const server=spawn('python3',['-m','http.server','4193','--bind','127.0.0.1'],{cwd:root,stdio:'ignore'});
await new Promise(r=>setTimeout(r,700));let browser;
try{
  browser=await playwright.chromium.launch({headless:true,executablePath:'/snap/bin/chromium',args:['--no-sandbox']});
  let revision=9, entries=[
    {date:'2026-08-17',schemaVersion:3,scaleMax:10,score:80,answers:{energy:8,focus:8,stress:2,calm:8,happiness:8},foundations:{sleepHours:8,sleepQuality:8,alcoholCount:0}},
    {date:'2026-08-18',schemaVersion:3,scaleMax:10,score:76,answers:{energy:8,focus:7,stress:3,calm:8,happiness:8},foundations:{sleepHours:6,alcoholCount:4}},
    {date:'2026-08-19',schemaVersion:3,scaleMax:10,score:30,answers:{energy:2,focus:3,stress:9,calm:3,happiness:6},foundations:{}}
  ], putBodies=[];
  const context=await browser.newContext({viewport:{width:390,height:844},serviceWorkers:'block'});
  const page=await context.newPage(),errors=[];page.on('pageerror',e=>errors.push(String(e)));
  await page.route(/.*\/(atlas|brain-atlas|injury-journal|private-health)\.js.*/,route=>route.fulfill({status:200,contentType:'application/javascript',body:''}));
  await page.route('**/api/health-checkins',async route=>{
    const request=route.request();
    if(request.method()==='GET')return route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({revision,entries})});
    if(request.method()==='PUT'){
      const body=request.postDataJSON();putBodies.push(body);const score=Math.round(((body.entry.answers.energy+body.entry.answers.focus+10-body.entry.answers.stress+body.entry.answers.calm+body.entry.answers.happiness)/50)*100);
      const saved={...body.entry,schemaVersion:3,scaleMax:10,score};entries=entries.filter(e=>e.date!==saved.date).concat(saved);revision++;
      return route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({revision,entries})});
    }
    return route.fulfill({status:405,body:'method'});
  });
  await page.goto('http://127.0.0.1:4193/health/',{waitUntil:'domcontentloaded'});
  await page.evaluate(()=>window.dispatchEvent(new CustomEvent('health:record-ready')));
  await page.waitForTimeout(1000);
  await page.waitForFunction(()=>document.querySelector('.energy-history-count')?.textContent.includes('3 entries'));
  assert.match(await page.locator('.energy-consistency-grid').textContent(),/Sleep under 7h[\s\S]*1 of 2/,'sleep missing state must not become zero');
  assert.match(await page.locator('.energy-consistency-grid').textContent(),/Alcohol 3\+[\s\S]*1 of 2/,'alcohol missing state must not become zero');
  await page.locator('.energy-calendar-prev').click();
  assert.equal(await page.locator('.energy-calendar-label').textContent(),'August 2026');
  assert.equal(await page.locator('.energy-calendar button.has-entry').count(),3);
  await page.locator('.energy-calendar button[data-date="2026-08-19"]').click();
  assert.match(await page.locator('.energy-day-detail').textContent(),/Sleep unknown · Alcohol unknown · Sleep quality unknown/);
  await page.screenshot({path:evidence+'/health-checkin-mobile-calendar.png',fullPage:true});

  await page.evaluate(()=>document.addEventListener('health:checkin',event=>window.__LAST_HEALTH_CHECKIN__=event.detail));
  await page.locator('.energy-checkin-open').click();
  const today=await page.locator('[name="date"]').inputValue();
  await page.locator('[name="energy"]').fill('9');await page.locator('[name="focus"]').fill('8');await page.locator('[name="stress"]').fill('2');await page.locator('[name="calm"]').fill('7');await page.locator('[name="happiness"]').fill('8');
  assert.equal(await page.locator('.energy-percent').textContent(),'80%','draft answers must preview on the visible battery');
  assert.equal(await page.locator('.energy-label').textContent(),'UNSAVED PREVIEW');
  assert.equal(await page.locator('.energy.energy-previewing').count(),1);
  assert.match(await page.locator('.energy-coverage').textContent(),/Save to update day, week and month history/);
  assert.deepEqual(await page.evaluate(()=>({answers:window.__LAST_HEALTH_CHECKIN__?.answers,draft:window.__LAST_HEALTH_CHECKIN__?.draft})),{answers:{energy:9,focus:8,stress:2,calm:7,happiness:8},draft:true},'brain event must carry the latest draft answers');
  await page.locator('[name="sleepHours"]').fill('7.5');await page.locator('[name="alcoholCount"]').fill('0');
  await page.locator('[name="happiness"]').press('Enter');await page.waitForFunction(()=>document.querySelector('.energy-feedback')?.textContent.includes('Saved privately'));
  assert.equal(putBodies.length,1);assert.equal(putBodies[0].revision,9);assert.equal(putBodies[0].entry.date,today);assert.equal(putBodies[0].entry.foundations.sleepHours,7.5);
  assert.equal(await page.locator('.energy-percent').textContent(),'80%','saved check-in must refresh the visible battery');
  assert.equal(await page.locator('.energy-label').textContent(),'ACCUMULATED BATTERY');
  assert.equal(await page.locator('.energy.energy-previewing').count(),0);
  await page.locator('.energy-checkin-open').click();await page.locator('[name="energy"]').fill('4');await page.locator('[name="focus"]').fill('5');await page.locator('[name="stress"]').fill('7');await page.locator('[name="calm"]').fill('4');await page.locator('[name="happiness"]').fill('4');
  assert.equal(await page.locator('.energy-percent').textContent(),'40%');assert.equal(await page.locator('.energy-label').textContent(),'UNSAVED PREVIEW');
  await page.locator('.energy-close').click();assert.equal(await page.locator('.energy-percent').textContent(),'80%','closing an unsaved draft must restore the saved battery');
  await page.locator('.energy-checkin-open').click();await page.locator('[name="energy"]').fill('4');await page.locator('[name="focus"]').fill('5');await page.locator('[name="stress"]').fill('7');await page.locator('[name="calm"]').fill('4');await page.locator('[name="happiness"]').fill('4');page.once('dialog',dialog=>dialog.accept());await page.locator('.energy-save').click();await page.waitForFunction(()=>document.querySelector('.energy-feedback')?.textContent.includes('Saved privately'));
  assert.equal(await page.locator('.energy-percent').textContent(),'40%','editing and saving must replace the visible battery immediately');
  await page.locator('[role="tab"][data-view="week"]').click();assert.equal(await page.locator('.energy-percent').textContent(),`${(40/7).toFixed(1)}%`,'week must recompute from the saved edit');
  await page.locator('[role="tab"][data-view="month"]').click();const monthDays=new Date(Number(today.slice(0,4)),Number(today.slice(5,7)),0).getDate();assert.equal(await page.locator('.energy-percent').textContent(),`${(40/monthDays).toFixed(1)}%`,'month must recompute from the saved edit');
  await page.locator('[role="tab"][data-view="day"]').click();
  await page.reload({waitUntil:'domcontentloaded'});await page.evaluate(()=>window.dispatchEvent(new CustomEvent('health:record-ready')));await page.waitForFunction(()=>document.querySelector('.energy-history-count')?.textContent.includes('4 entries'));
  assert.equal(await page.locator('.energy-percent').textContent(),'40%','edited score must survive mocked server reload');
  assert.equal(await page.locator(`.energy-calendar button[data-date="${today}"]`).getAttribute('aria-label'),`${today}, 40% battery`,'mocked server readback must survive reload');

  await page.setViewportSize({width:1440,height:1000});await page.locator('.energy-checkin-open').click();await page.locator('.energy-save').scrollIntoViewIfNeeded();await page.screenshot({path:evidence+'/health-checkin-desktop-update.png'});
  const footer=await page.locator('.energy-form-footer').boundingBox(),button=await page.locator('.energy-save').boundingBox();assert(footer&&button&&button.x>footer.x+footer.width/2,'Update must remain at the form footer bottom right');
  assert.equal(await page.locator('.energy-save').textContent(),'UPDATE');assert.equal(errors.length,0,errors.join('\n'));
  console.log('PASS mocked private UI: Enter submit, save, battery refresh, revision readback reload, prior-month calendar, selectable details, unknown states, consistency, mobile/desktop');
}finally{if(browser)await browser.close();server.kill('SIGTERM')}
