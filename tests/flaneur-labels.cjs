const { test } = require('node:test');
const assert = require('node:assert/strict');
const { chromium, webkit } = require('/root/clawd/novaire-operations-system/node_modules/playwright');
const fs = require('fs');
const base = process.env.FLANEUR_URL || 'http://127.0.0.1:8765/map/index.html';
const artifacts = process.env.FLANEUR_ARTIFACTS || '/root/clawd/artifacts/flaneur-physical-layers';
fs.mkdirSync(artifacts,{recursive:true});

async function open(type,viewport,mobile=false){
  const browser=await type.launch({headless:true});
  const page=await browser.newPage({viewport,hasTouch:mobile,isMobile:mobile});
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto(base,{waitUntil:'domcontentloaded'});
  await page.waitForSelector('#globe-canvas[data-ready="true"]');
  await page.waitForFunction(()=>{const n=document.querySelector('#globe-canvas');return n.dataset.physicalSource&&n.dataset.labelCoverage});
  return {browser,page,errors};
}
async function focus(page,country,zooms=1){
  await page.locator('#reset-view').evaluate(n=>n.click());
  await page.fill('#search',country);await page.locator('.country-row').filter({hasText:country}).first().click();
  await page.locator('#tooltip').evaluate(n=>n.classList.remove('show'));
  for(let i=0;i<zooms;i++)await page.locator('#globe-canvas').press('+');
  await page.waitForTimeout(650);
  return page.locator('#globe-canvas').evaluate(n=>({labels:n.dataset.labels,zoom:+n.dataset.zoom,coverage:JSON.parse(n.dataset.labelCoverage||'{}'),source:n.dataset.physicalSource,rotation:n.dataset.rotation,selected:n.dataset.selectedCode}));
}

async function assertLabelSafety(page,context){
  const state=await page.locator('#globe-canvas').evaluate(canvas=>{
    const canvasRect=canvas.getBoundingClientRect(),inCanvas=rect=>({left:rect.left-canvasRect.left,top:rect.top-canvasRect.top,right:rect.right-canvasRect.left,bottom:rect.bottom-canvasRect.top});
    return {width:canvasRect.width,height:canvasRect.height,boxes:[...JSON.parse(canvas.dataset.labelBoxes||'[]'),...JSON.parse(canvas.dataset.admin1Boxes||'[]')],controls:[...document.querySelectorAll('.legend,.zoom,.source-note')].filter(el=>getComputedStyle(el).display!=='none').map(el=>inCanvas(el.getBoundingClientRect()))};
  });
  const overlap=(a,b)=>a.left<b.right&&a.right>b.left&&a.top<b.bottom&&a.bottom>b.top;
  assert.ok(state.boxes.length,`${context}: exposes rendered label boxes`);
  for(const box of state.boxes){
    assert.ok(box.left>=6&&box.right<=state.width-6&&box.top>=6&&box.bottom<=state.height-6,`${context}: ${box.name} full bbox inside canvas: ${JSON.stringify(box)}`);
    for(const control of state.controls)assert.equal(overlap(box,control),false,`${context}: ${box.name} avoids UI: ${JSON.stringify({box,control})}`);
  }
}

test('only curated major water and terrain labels reveal progressively with projected relief',async()=>{
  const {browser,page,errors}=await open(chromium,{width:1440,height:1000});
  try{
    const canvas=page.locator('#globe-canvas');
    const overview=await canvas.evaluate(n=>({labels:n.dataset.labels.split('|'),water:+n.dataset.labelWater,lakes:+n.dataset.labelLakes,terrain:+n.dataset.labelTerrain,source:n.dataset.physicalSource}));
    assert.equal(overview.source,'ready');assert.ok(overview.water>=1);assert.equal(overview.lakes,0);assert.equal(overview.terrain,0);assert.ok(overview.labels.length<=5,JSON.stringify(overview));
    await canvas.screenshot({path:`${artifacts}/overview-desktop.png`});
    const cases=[['Ukraine','Black Sea','black-sea-caucasus'],['United States','Rocky Mountains','usa-rockies'],['Chile','Andes','andes']];
    for(const [country,label,file] of cases){const state=await focus(page,country,2);assert.match(state.labels,new RegExp(label),`${file}: ${JSON.stringify(state)}`);assert.doesNotMatch(state.labels,/Lake|Caspian Sea/);assert.deepEqual(state.coverage,{water:18,lake:0,terrain:222});await canvas.screenshot({path:`${artifacts}/${file}.png`});}
    assert.deepEqual(errors,[]);
  }finally{await browser.close()}
});

test('US and Canadian admin-1 appears only at deep zoom and remains country-selectable',async()=>{
  const {browser,page,errors}=await open(chromium,{width:1440,height:1000});try{
    const canvas=page.locator('#globe-canvas');let state=await canvas.evaluate(n=>({source:n.dataset.admin1Source||'',outlines:+(n.dataset.admin1Outlines||0),labels:+(n.dataset.admin1Labels||0)}));
    assert.equal(state.source,'');assert.equal(state.outlines,0);assert.equal(state.labels,0);
    await focus(page,'United States',4);await page.waitForFunction(()=>document.querySelector('#globe-canvas').dataset.admin1Source==='ready');
    state=await canvas.evaluate(n=>({coverage:JSON.parse(n.dataset.admin1Coverage),outlines:+n.dataset.admin1Outlines,labels:+n.dataset.admin1Labels,names:n.dataset.admin1Names,selected:n.dataset.selectedCode}));
    assert.deepEqual(state.coverage,{US:51,CA:13});assert.ok(state.outlines>20);assert.ok(state.labels>10);assert.equal(state.selected,'US');assert.match(state.names,/Texas|California/);
    await canvas.screenshot({path:`${artifacts}/admin1-us-desktop.png`});
    for(let i=0;i<6;i++)await canvas.press('ArrowRight');for(let i=0;i<2;i++)await canvas.press('ArrowDown');await page.waitForTimeout(100);state=await canvas.evaluate(n=>({names:n.dataset.admin1Names,selected:n.dataset.selectedCode}));assert.match(state.names,/Alaska/);assert.equal(state.selected,'US');
    await canvas.screenshot({path:`${artifacts}/admin1-alaska-antimeridian.png`});
    const hawaii=await focus(page,'Hawaii',0);assert.equal(hawaii.selected,'US');assert.match(await canvas.getAttribute('data-admin1-names'),/Hawaii/);await canvas.screenshot({path:`${artifacts}/admin1-hawaii.png`});
    await focus(page,'Canada',4);state=await canvas.evaluate(n=>({names:n.dataset.admin1Names,selected:n.dataset.selectedCode}));assert.equal(state.selected,'CA');assert.match(state.names,/Ontario|Alberta/);await canvas.screenshot({path:`${artifacts}/admin1-canada-desktop.png`});
    assert.deepEqual(errors,[]);
  }finally{await browser.close()}
});

for(const [width,name] of [[320,'mobile-320'],[390,'mobile-390']])test(`${name} remains uncluttered and interactive`,async()=>{
  const {browser,page,errors}=await open(chromium,{width,height:844},true);try{
    const canvas=page.locator('#globe-canvas');const initial=await canvas.evaluate(n=>({diameter:+n.dataset.diameter,labels:n.dataset.labels.split('|').filter(Boolean),rotation:n.dataset.rotation}));
    assert.ok(initial.diameter<=width-16);assert.ok(initial.labels.length<=4);
    const black=await focus(page,'Ukraine',2);assert.match(black.labels,/Black Sea/);assert.match(black.labels,/Caucasus Mountains/);
    await assertLabelSafety(page,`${name} Black Sea focus`);
    await canvas.screenshot({path:`${artifacts}/${name}-black-sea.png`});
    await focus(page,'Canada',4);await page.waitForFunction(()=>document.querySelector('#globe-canvas').dataset.admin1Source==='ready');await assertLabelSafety(page,`${name} Canada admin-1`);assert.equal(await canvas.getAttribute('data-selected-code'),'CA');await canvas.screenshot({path:`${artifacts}/${name}-canada-admin1.png`});
    await page.touchscreen.tap((await canvas.boundingBox()).x+width/2,(await canvas.boundingBox()).y+200);assert.ok(await page.locator('#tooltip').count());
    assert.deepEqual(errors,[]);
  }finally{await browser.close()}
});

test('desktop geography labels stay fully visible and clear of controls',async()=>{
  const {browser,page,errors}=await open(chromium,{width:1440,height:1000});try{
    await focus(page,'Ukraine',2);await assertLabelSafety(page,'desktop Black Sea focus');
    assert.deepEqual(errors,[]);
  }finally{await browser.close()}
});

test('WebKit loads optional physical layers and keeps country selection',async t=>{
  let session;try{session=await open(webkit,{width:390,height:844},true)}catch(e){t.skip(`WebKit unavailable: ${e.message}`);return}
  const {browser,page,errors}=session;try{const state=await focus(page,'Georgia',2);assert.equal(state.source,'ready');assert.match(state.labels,/Black Sea/);assert.equal(state.selected,'GE');assert.deepEqual(errors,[]);await page.locator('#globe-canvas').screenshot({path:`${artifacts}/webkit-caucasus.png`});}finally{await browser.close()}
});

test('optional physical asset failure keeps the base globe usable',async()=>{
  const browser=await chromium.launch({headless:true});const page=await browser.newPage({viewport:{width:390,height:844}});
  await page.route(/physical-labels\.json|natural-earth-relief\.webp/,route=>route.abort());await page.goto(base);await page.waitForSelector('#globe-canvas[data-ready="true"]');await page.waitForFunction(()=>document.querySelector('#globe-canvas').dataset.physicalSource==='fallback');
  const state=await page.locator('#globe-canvas').evaluate(n=>({ready:n.dataset.ready,features:+n.dataset.visibleFeatures,labels:n.dataset.labels,boxes:JSON.parse(n.dataset.labelBoxes||'[]')}));assert.equal(state.ready,'true');assert.ok(state.features>100);assert.ok(Array.isArray(state.boxes));await browser.close();
});
