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
async function openDesktopAt(type,{width=1298,height=929,deviceScaleFactor=2,reducedMotion='no-preference'}={}) {
  const browser=await type.launch({headless:true});
  const context=await browser.newContext({viewport:{width,height},deviceScaleFactor,reducedMotion});
  const page=await context.newPage();
  page.on('pageerror',e=>errors.push(`${type.name()}: pageerror: ${e.message}`));
  page.on('console',m=>{if(m.type()==='error')errors.push(`${type.name()}: console: ${m.text()}`)});
  await page.goto(base,{waitUntil:'domcontentloaded'});await page.waitForSelector('#globe-canvas[data-ready="true"]');
  return {browser,page};
}
async function tapFocusedCountry(page,canvas,code){
  await canvas.scrollIntoViewIfNeeded();const box=await canvas.boundingBox(),cx=box.x+box.width/2,cy=box.y+(45+box.height-28)/2;
  for(let radius=0;radius<=50;radius+=10)for(let dy=-radius;dy<=radius;dy+=10)for(let dx=-radius;dx<=radius;dx+=10){await page.mouse.click(cx+dx,cy+dy);if(await page.locator('#selection-canvas').getAttribute('data-selected')===code)return}
  assert.fail(`could not tap focused ${code}`);
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
async function selectionPixels(page){return page.locator('#selection-canvas').evaluate(c=>{const d=c.getContext('2d').getImageData(0,0,c.width,c.height).data;let n=0;for(let i=3;i<d.length;i+=4)if(d[i])n++;return n})}

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

test('country facts require a fresh tap and dismiss on any touch, drag, pinch or scroll', async () => {
  const {browser,page}=await open(chromium);
  try {
    const canvas=page.locator('#globe-canvas'),box=await canvas.boundingBox(),client=await page.context().newCDPSession(page);
    const x=box.x+box.width*.50,y=box.y+box.height*.50;
    await page.touchscreen.tap(x,y);
    const tip=page.locator('.tooltip');
    await assert.doesNotReject(()=>tip.waitFor({state:'visible'}),'country tap opens facts');
    for(const label of ['Capital:','Population:','GDP:'])assert.match(await tip.innerText(),new RegExp(label));

    await client.send('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[touch(20,20,71)]});
    assert.equal(await tip.evaluate(el=>el.classList.contains('show')),false,'touchstart anywhere dismisses facts before movement or scroll');
    await client.send('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]});
    await page.waitForTimeout(50);
    assert.equal(await tip.evaluate(el=>el.classList.contains('show')),false,'touch release outside globe cannot reopen facts');

    await page.touchscreen.tap(x,y);
    assert.equal(await tip.evaluate(el=>el.classList.contains('show')),true,'intentional fresh country tap reopens facts');
    await client.send('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[touch(x-65,y,72)]});
    assert.equal(await tip.evaluate(el=>el.classList.contains('show')),false,'globe pointerdown immediately dismisses facts');
    for(let i=1;i<=10;i++)await client.send('Input.dispatchTouchEvent',{type:'touchMove',touchPoints:[touch(x-65+i*12,y,72)]});
    await client.send('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]});
    await page.waitForTimeout(50);
    assert.equal(await tip.evaluate(el=>el.classList.contains('show')),false,'drag release remains hidden');

    const movedBox=await canvas.boundingBox(),mx=movedBox.x+movedBox.width/2,my=movedBox.y+movedBox.height/2;
    await page.touchscreen.tap(mx,my);
    assert.equal(await tip.evaluate(el=>el.classList.contains('show')),true,'fresh tap after drag reopens facts');
    await client.send('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[touch(mx-55,my,73),touch(mx+55,my,74)]});
    assert.equal(await tip.evaluate(el=>el.classList.contains('show')),false,'pinch start immediately dismisses facts');
    for(let i=1;i<=8;i++)await client.send('Input.dispatchTouchEvent',{type:'touchMove',touchPoints:[touch(mx-55-i*3,my,73),touch(mx+55+i*3,my,74)]});
    await client.send('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]});
    await page.waitForTimeout(50);
    assert.equal(await tip.evaluate(el=>el.classList.contains('show')),false,'pinch release remains hidden');
    await page.evaluate(({mx,my})=>document.querySelector('#globe-canvas').dispatchEvent(new PointerEvent('pointermove',{pointerId:99,pointerType:'mouse',clientX:mx,clientY:my,bubbles:true})),{mx,my});
    assert.equal(await tip.evaluate(el=>el.classList.contains('show')),false,'synthetic mouse hover after touch cannot reopen facts');

    await page.touchscreen.tap(mx,my);
    assert.equal(await tip.evaluate(el=>el.classList.contains('show')),true,'fresh tap after pinch reopens facts');
    await page.evaluate(()=>scrollBy(0,Math.max(320,innerHeight*.6)));
    await page.waitForFunction(()=>!document.querySelector('#tooltip').classList.contains('show'));
    assert.equal(await tip.evaluate(el=>el.classList.contains('show')),false,'page scroll dismisses facts');
    await canvas.scrollIntoViewIfNeeded();
    const reopenedBox=await canvas.boundingBox();
    await page.touchscreen.tap(reopenedBox.x+reopenedBox.width*.50,reopenedBox.y+reopenedBox.height*.50);
    await assert.doesNotReject(()=>tip.waitFor({state:'visible'}),'country tap reopens facts after scroll dismissal');
    assert.match(await tip.innerText(),/Capital: .+/);
  } finally {await browser.close();}
});

test('trusted mobile routing dismisses stale facts, scrolls vertically, rotates horizontally and pinches', async () => {
  const {browser,page}=await open(chromium);
  try {
    const canvas=page.locator('#globe-canvas'),box=await canvas.boundingBox(),client=await page.context().newCDPSession(page);
    const cx=box.x+box.width/2,cy=box.y+box.height/2;
    await page.touchscreen.tap(cx,cy);
    assert.equal(await page.locator('.tooltip.show').count(),1,'country facts are visible before a new gesture');

    const rotationBeforeScroll=await canvas.getAttribute('data-rotation');
    await client.send('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[touch(cx,cy+70,41)]});
    await page.waitForTimeout(20);
    assert.equal(await page.locator('.tooltip.show').count(),0,'touchstart immediately dismisses stale country facts');
    for(let i=1;i<=10;i++)await client.send('Input.dispatchTouchEvent',{type:'touchMove',touchPoints:[touch(cx,cy+70-i*14,41)]});
    await client.send('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]});
    await page.waitForTimeout(100);
    assert.ok(await page.evaluate(()=>scrollY)>40,'vertical swipe over globe routes to page scroll');
    assert.equal(await canvas.getAttribute('data-rotation'),rotationBeforeScroll,'vertical page swipe does not also rotate globe');

    await canvas.scrollIntoViewIfNeeded();const routedBox=await canvas.boundingBox(),routedY=routedBox.y+routedBox.height/2;
    const scrollBeforeDrag=await page.evaluate(()=>scrollY),rotationBeforeDrag=await canvas.getAttribute('data-rotation');
    await client.send('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[touch(routedBox.x+100,routedY,51)]});
    for(let i=1;i<=16;i++){await client.send('Input.dispatchTouchEvent',{type:'touchMove',touchPoints:[touch(routedBox.x+100+i*8,routedY+i*.35,51)]});await page.waitForTimeout(16);}
    await client.send('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]});await page.waitForTimeout(50);
    assert.notEqual(await canvas.getAttribute('data-rotation'),rotationBeforeDrag,'horizontal swipe rotates globe');
    assert.equal(await page.evaluate(()=>scrollY),scrollBeforeDrag,'horizontal globe drag does not scroll page');

    const zoomBefore=Number(await canvas.getAttribute('data-zoom'));
    await client.send('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[touch(routedBox.x+140,routedY,61),touch(routedBox.x+250,routedY,62)]});
    for(let i=1;i<=12;i++){await client.send('Input.dispatchTouchEvent',{type:'touchMove',touchPoints:[touch(routedBox.x+140-i*3,routedY,61),touch(routedBox.x+250+i*3,routedY,62)]});await page.waitForTimeout(16);}
    await client.send('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]});await page.waitForTimeout(50);
    assert.ok(Number(await canvas.getAttribute('data-zoom'))>zoomBefore*1.4,'two-finger pinch zoom remains responsive');
    assert.equal(await page.locator('.tooltip.show').count(),0,'pinch cannot leave stale facts over page content');
    await page.screenshot({path:`${artifacts}/chromium-mobile-routing.png`,fullPage:true});
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

test('desktop mouse drag, wheel, tap-only facts, directory focus and draw budget', async () => {
  const {browser,page}=await open(chromium,false);
  try {
    const canvas=page.locator('#globe-canvas'),box=await canvas.boundingBox();
    const initial=await paintStats(page);
    await page.mouse.move(box.x+box.width*.50,box.y+box.height*.52);
    assert.equal(await page.locator('.tooltip.show').count(),0,'mouse hover cannot open country facts');
    await page.mouse.down();
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

test('zoom selects culled detail geometry without losing painted islands', async () => {
  const {browser,page}=await open(chromium,false);
  try {
    const canvas=page.locator('#globe-canvas');
    assert.equal(await canvas.getAttribute('data-lod'),'medium','standard desktop gets scale-appropriate medium geometry');
    await page.fill('#search','Cuba');await page.locator('.country-row[data-code="CU"]').click();
    await canvas.scrollIntoViewIfNeeded();await page.evaluate(()=>document.querySelector('#zoom-in').click());
    assert.equal(await canvas.getAttribute('data-lod'),'detail');
    const visible=Number(await canvas.getAttribute('data-visible-features'));
    assert.ok(visible>10&&visible<100,`high zoom uses conservative visible-region culling: ${visible}`);
    const painted=await paintStats(page);assert.ok(painted.land+painted.visited+painted.calling>3000,'detailed Caribbean remains painted');
    await canvas.screenshot({path:`${artifacts}/chromium-caribbean-detail.png`});
  } finally {await browser.close();}
});

test('effective projected scale selects settled detail without wheel zoom at user desktop scale', async () => {
  const {browser,page}=await openDesktopAt(chromium);
  try {
    const canvas=page.locator('#globe-canvas');
    assert.equal(await canvas.getAttribute('data-zoom'),'1.0000','test begins without relative wheel zoom');
    assert.equal(await canvas.getAttribute('data-lod'),'detail','large DPR viewport receives detail geometry immediately');
    assert.ok(Number(await canvas.getAttribute('data-projected-scale'))>=600,'LOD uses effective projected raster scale');
    await page.waitForTimeout(250);
    const pixels=await paintStats(page);assert.ok(pixels.land+pixels.visited+pixels.calling>10000,'settled high-quality frame retains painted geography');
    await page.screenshot({path:`${artifacts}/user-scale-asia-pacific-detail.png`,fullPage:true});
  } finally {await browser.close()}
});

for(const reducedMotion of ['no-preference','reduce'])test(`country selection highlight replaces, persists and clears (${reducedMotion})`,async()=>{
  const {browser,page}=await openDesktopAt(chromium,{reducedMotion});
  try{
    const canvas=page.locator('#globe-canvas'),overlay=page.locator('#selection-canvas');
    await page.fill('#search','Japan');await page.locator('.country-row[data-code="JP"]').click();await page.waitForTimeout(50);
    await tapFocusedCountry(page,canvas,'JP');
    assert.equal(await overlay.getAttribute('data-selected'),'JP','tap highlights selected country');
    assert.ok(await selectionPixels(page)>500,'selected country overlay paints a visible highlight');
    assert.equal(await page.locator('.tooltip.show').count(),1,'highlight persists while facts are open');
    assert.equal(await overlay.getAttribute('data-motion'),reducedMotion==='reduce'?'static':'pulse','motion preference controls initial highlight');
    if(reducedMotion==='no-preference'){await page.waitForTimeout(1000);assert.equal(await overlay.getAttribute('data-motion'),'settled','pulse settles to persistent outline')}
    await page.mouse.click(4,4);assert.equal(await overlay.getAttribute('data-selected'),'','facts dismissal clears highlight');
    await page.fill('#search','Australia');await page.locator('.country-row[data-code="AU"]').click();await page.waitForTimeout(50);await tapFocusedCountry(page,canvas,'AU');
    assert.equal(await overlay.getAttribute('data-selected'),'AU','next tap replaces selected country');
    if(reducedMotion==='no-preference')await page.screenshot({path:`${artifacts}/user-scale-australia-selected.png`,fullPage:true});
  }finally{await browser.close()}
});

test('tiny country selection receives an identifiable marker highlight',async()=>{
  const {browser,page}=await openDesktopAt(chromium);
  try{const canvas=page.locator('#globe-canvas');await page.fill('#search','Singapore');await page.locator('.country-row[data-code="SG"]').click();await page.waitForTimeout(50);await tapFocusedCountry(page,canvas,'SG');assert.equal(await page.locator('#selection-canvas').getAttribute('data-selected'),'SG');assert.ok(await selectionPixels(page)>80,'microstate marker paints visible pixels')}finally{await browser.close()}
});

async function expectCount(locator,count){assert.equal(await locator.count(),count);}

test.after(()=>assert.deepEqual(errors,[],`browser errors:\n${errors.join('\n')}`));
