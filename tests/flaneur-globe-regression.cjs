const { test } = require('node:test');
const assert = require('node:assert/strict');
const { chromium, webkit } = require('/root/clawd/novaire-operations-system/node_modules/playwright');

const base = process.env.FLANEUR_URL || 'http://127.0.0.1:8765/map/index.html';
const artifacts = process.env.FLANEUR_ARTIFACTS || '/root/clawd/artifacts/flaneur-fixed';
require('fs').mkdirSync(artifacts,{recursive:true});
const errors = [];

function touch(x, y, id) { return {x, y, id, radiusX: 5, radiusY: 5, force: 1}; }
async function open(type, mobile = true) {
  const browser = await type.launch({headless: true});
  const context = await browser.newContext(mobile ? {viewport:{width:390,height:844},hasTouch:true,isMobile:true} : {viewport:{width:1440,height:1000}});
  const page = await context.newPage();
  page.on('pageerror', e => errors.push(`${type.name()}: pageerror: ${e.message}`));
  page.on('console', m => { if (m.type() === 'error') errors.push(`${type.name()}: console: ${m.text()}`); });
  await page.goto(base, {waitUntil:'domcontentloaded'});
  await page.waitForSelector('#globe-canvas[data-ready="true"]');
  return {browser,page};
}
async function paintStats(page) {
  return page.locator('#globe-canvas').evaluate(canvas => {
    const ctx=canvas.getContext('2d'), d=ctx.getImageData(0,0,canvas.width,canvas.height).data;
    let land=0,visited=0,calling=0;
    for(let i=0;i<d.length;i+=4){
      if(d[i]===102&&d[i+1]===112&&d[i+2]===107&&d[i+3])land++;
      if(d[i]===35&&d[i+1]===122&&d[i+2]===78&&d[i+3])visited++;
      if(d[i]===166&&d[i+1]===95&&d[i+2]===46&&d[i+3])calling++;
    }
    return {land,visited,calling,width:canvas.width,height:canvas.height};
  });
}

for (const type of [chromium, webkit]) test(`${type.name()} keeps painted status land through trusted touch gestures`, async t => {
  let session;
  try { session=await open(type); } catch(e) { if(type===webkit){t.skip(`WebKit unavailable: ${e.message}`);return;} throw e; }
  const {browser,page}=session;
  try {
    const canvas=page.locator('#globe-canvas'), box=await canvas.boundingBox(), cy=box.y+box.height/2;
    const initial=await paintStats(page);
    assert.ok(initial.land>1000&&initial.visited>1000&&initial.calling>10,`all status colours painted initially: ${JSON.stringify(initial)}`);
    assert.equal(await canvas.getAttribute('data-diameter'),'374','approved 390px globe diameter');
    await page.touchscreen.tap(box.x+box.width*.50,cy);
    const trustedTip=await page.locator('.tooltip.show').innerText();
    for(const label of ['Capital:','Population:','GDP:'])assert.match(trustedTip,new RegExp(label),`trusted ${type.name()} tap shows ${label}`);
    if(type===chromium){
      const client=await page.context().newCDPSession(page);
      await client.send('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[touch(box.x+95,cy,1)]});
      for(let i=1;i<=24;i++){
        await client.send('Input.dispatchTouchEvent',{type:'touchMove',touchPoints:[touch(box.x+95+i*6,cy+i*.5,1)]});await page.waitForTimeout(16);
        if(i%6===0){const s=await paintStats(page);assert.ok(s.land+s.visited+s.calling>2000,`land stays painted at drag step ${i}: ${JSON.stringify(s)}`);}
      }
      await client.send('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]});
      const afterDrag=await paintStats(page);assert.ok(afterDrag.land+afterDrag.visited+afterDrag.calling>2000,'land painted after drag');
      await client.send('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[touch(box.x+125,cy,11),touch(box.x+265,cy,12)]});
      for(let i=1;i<=12;i++)await client.send('Input.dispatchTouchEvent',{type:'touchMove',touchPoints:[touch(box.x+125-i*3,cy,11),touch(box.x+265+i*3,cy,12)]});
      const duringPinch=await paintStats(page);assert.ok(duringPinch.land+duringPinch.visited+duringPinch.calling>2000,'land painted during pinch');
      await client.send('Input.dispatchTouchEvent',{type:'touchCancel',touchPoints:[]});
    } else {
      await page.touchscreen.tap(box.x+box.width/2,cy);
    }
    const afterCancel=await paintStats(page);assert.ok(afterCancel.land+afterCancel.visited+afterCancel.calling>2000,'land painted after cancel');
    const perf=await page.evaluate(()=>{const a=window.__flaneurPerf.draws.slice(2).sort((x,y)=>x-y);return {count:a.length,mean:a.reduce((x,y)=>x+y,0)/a.length,p95:a[Math.floor(a.length*.95)],max:a[a.length-1]}});
    if(type===chromium){assert.ok(perf.count>=15,`profiled 60Hz mobile frames: ${JSON.stringify(perf)}`);assert.ok(perf.p95<33,`mobile p95 draw inside interaction budget: ${JSON.stringify(perf)}`);require('fs').writeFileSync(`${artifacts}/mobile-performance.json`,JSON.stringify(perf,null,2));}
    await page.screenshot({path:`${artifacts}/${type.name()}-mobile.png`,fullPage:true});
  } finally {await browser.close();}
});

test('canvas pointerup hit testing shows complete facts after consecutive slight taps', async () => {
  const {browser,page}=await open(chromium);
  try {
    const result=await page.evaluate(async()=>{
      const c=document.querySelector('#globe-canvas'),b=c.getBoundingClientRect();
      const fire=(type,id,x,y)=>c.dispatchEvent(new PointerEvent(type,{pointerId:id,pointerType:'touch',button:0,clientX:x,clientY:y,bubbles:true}));
      const taps=[];
      for(let id=31;id<=33;id++){
        const x=b.left+b.width*.56,y=b.top+b.height*.52;
        fire('pointerdown',id,x,y);fire('pointermove',id,x+2,y+1);fire('pointerup',id,x+2,y+1);
        taps.push(document.querySelector('#tooltip').innerText);
      }
      return taps;
    });
    for(const text of result){assert.match(text,/Capital: .+/);assert.match(text,/Population: .+ \(\d{4}\) · #\d+/);assert.match(text,/GDP: .+ \(\d{4}\) · #\d+/);}
  } finally {await browser.close();}
});

test('desktop mouse drag, wheel, hover facts, directory focus and draw budget', async () => {
  const {browser,page}=await open(chromium,false);
  try {
    const canvas=page.locator('#globe-canvas'),box=await canvas.boundingBox();
    const initial=await paintStats(page);
    await page.mouse.move(box.x+box.width*.50,box.y+box.height*.52);await page.mouse.down();
    for(let i=1;i<=60;i++){await page.mouse.move(box.x+box.width*.50+i*3,box.y+box.height*.52+i*.3);await page.waitForTimeout(16);}
    await page.mouse.up();
    const after=await paintStats(page);assert.ok(after.land+after.visited+after.calling>2000,'desktop drag keeps land painted');
    await page.mouse.move(box.x+box.width*.52,box.y+box.height*.52);await page.mouse.wheel(0,-400);await page.waitForTimeout(50);
    const zoomed=Number(await canvas.getAttribute('data-diameter'));
    await page.fill('#search','Japan');await page.locator('.country-row[data-code="JP"]').click();await page.waitForTimeout(50);
    assert.ok((await paintStats(page)).land>1000,'directory focus keeps map visible');
    const perf=await page.evaluate(()=>{const a=window.__flaneurPerf.draws.slice(2).sort((x,y)=>x-y);return {count:a.length,mean:a.reduce((x,y)=>x+y,0)/a.length,p95:a[Math.floor(a.length*.95)],max:a[a.length-1]}});
    assert.ok(perf.count>=30,`profiled realistic movement frames: ${JSON.stringify(perf)}`);
    assert.ok(perf.p95<33,`p95 draw is inside interaction budget: ${JSON.stringify(perf)}`);
    await page.screenshot({path:`${artifacts}/chromium-desktop.png`,fullPage:true});
    require('fs').writeFileSync(`${artifacts}/performance.json`,JSON.stringify({initial,after,zoomed,perf},null,2));
  } finally {await browser.close();}
});

test('canonical branding and globe-only wheel capture', async () => {
  const {browser,page}=await open(chromium,false);
  try {
    const header=page.locator('.topbar .signal-brand-row'),footer=page.locator('footer .signal-brand-row');
    for(const row of [header,footer]){
      await expectCount(row.locator('.signal-map-icon'),1);
      await expectCount(row.locator('.signal-bolt-icon'),1);
      assert.equal(await row.locator('.signal-map').getAttribute('href'),'/flaneur');
      assert.equal(await row.locator('.signal-bolt').getAttribute('href'),'/portfolio/');
      assert.equal(await row.evaluate(e=>getComputedStyle(e).gap),'12px');
    }
    assert.ok(!await page.locator('body').innerText().then(t=>t.includes('A living record · 195 countries + 4 destinations')),'removed descriptive edition copy');
    const canvas=page.locator('#globe-canvas'),box=await canvas.boundingBox();
    const initialZoom=await canvas.getAttribute('data-zoom');
    await page.mouse.move(box.x+8,box.y+box.height/2);await page.mouse.wheel(0,500);await page.waitForTimeout(100);
    assert.ok(await page.evaluate(()=>scrollY)>0,'wheel in side gutter scrolls page');
    assert.equal(await canvas.getAttribute('data-zoom'),initialZoom,'side gutter does not zoom globe');
    await page.evaluate(()=>scrollTo(0,0));
    await page.mouse.move(box.x+box.width/2,box.y+box.height/2);await page.mouse.wheel(0,-400);await page.waitForTimeout(100);
    assert.ok(Number(await canvas.getAttribute('data-zoom'))>Number(initialZoom),'wheel over projected sphere zooms globe');
    assert.equal(await page.evaluate(()=>scrollY),0,'sphere wheel is captured from page scroll');
    await page.locator('.topbar').screenshot({path:`${artifacts}/chromium-desktop-header.png`});
    await page.locator('footer').screenshot({path:`${artifacts}/chromium-desktop-footer.png`});
  } finally {await browser.close();}
});

async function expectCount(locator,count){assert.equal(await locator.count(),count);}

test.after(()=>assert.deepEqual(errors,[],`browser errors:\n${errors.join('\n')}`));
