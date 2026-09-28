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
  await page.waitForTimeout(120);
  return page.locator('#globe-canvas').evaluate(n=>({labels:n.dataset.labels,zoom:+n.dataset.zoom,coverage:JSON.parse(n.dataset.labelCoverage||'{}'),source:n.dataset.physicalSource,rotation:n.dataset.rotation,selected:n.dataset.selectedCode}));
}

test('Natural Earth water and terrain labels reveal progressively with projected relief',async()=>{
  const {browser,page,errors}=await open(chromium,{width:1440,height:1000});
  try{
    const canvas=page.locator('#globe-canvas');
    const overview=await canvas.evaluate(n=>({labels:n.dataset.labels.split('|'),water:+n.dataset.labelWater,lakes:+n.dataset.labelLakes,terrain:+n.dataset.labelTerrain,source:n.dataset.physicalSource}));
    assert.equal(overview.source,'ready');assert.ok(overview.water>=1);assert.equal(overview.lakes,0);assert.equal(overview.terrain,0);assert.ok(overview.labels.length<=5,JSON.stringify(overview));
    await canvas.screenshot({path:`${artifacts}/overview-desktop.png`});
    const cases=[['Ukraine','Black Sea','black-sea-caspian-caucasus'],['United States','Lake Superior','great-lakes-rockies'],['Mongolia','Lake Baikal','baikal'],['Uganda','Lake Victoria','victoria'],['Chile','Andes','andes']];
    for(const [country,label,file] of cases){const state=await focus(page,country,2);assert.match(state.labels,new RegExp(label),`${file}: ${JSON.stringify(state)}`);if(file==='black-sea-caspian-caucasus'){assert.match(state.labels,/Caspian Sea/);assert.match(state.labels,/Caucasus Mountains/)}assert.deepEqual(state.coverage,{water:295,lake:745,terrain:222});await canvas.screenshot({path:`${artifacts}/${file}.png`});}
    assert.deepEqual(errors,[]);
  }finally{await browser.close()}
});

for(const [width,name] of [[320,'mobile-320'],[390,'mobile-390']])test(`${name} remains uncluttered and interactive`,async()=>{
  const {browser,page,errors}=await open(chromium,{width,height:844},true);try{
    const canvas=page.locator('#globe-canvas');const initial=await canvas.evaluate(n=>({diameter:+n.dataset.diameter,labels:n.dataset.labels.split('|').filter(Boolean),rotation:n.dataset.rotation}));
    assert.ok(initial.diameter<=width-16);assert.ok(initial.labels.length<=4);
    const black=await focus(page,'Ukraine',2);assert.match(black.labels,/Black Sea/);
    await canvas.screenshot({path:`${artifacts}/${name}-black-sea.png`});
    await page.touchscreen.tap((await canvas.boundingBox()).x+width/2,(await canvas.boundingBox()).y+200);assert.ok(await page.locator('#tooltip').count());
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
  const state=await page.locator('#globe-canvas').evaluate(n=>({ready:n.dataset.ready,features:+n.dataset.visibleFeatures,labels:n.dataset.labels}));assert.equal(state.ready,'true');assert.ok(state.features>100);assert.match(state.labels,/Atlantic Ocean|Indian Ocean/);await browser.close();
});
