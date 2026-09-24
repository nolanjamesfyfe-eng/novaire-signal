const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const {chromium}=require('/root/clawd/novaire-operations-system/node_modules/playwright');
const base=process.env.FLANEUR_URL||'http://127.0.0.1:8765/map/index.html';
const artifacts=process.env.FLANEUR_ARTIFACTS||'/root/clawd/novaire-signal/qa-artifacts/flaneur-deep-zoom';
fs.mkdirSync(artifacts,{recursive:true});

async function open(viewport, mobile=false){
  const browser=await chromium.launch({headless:true});
  const context=await browser.newContext({viewport,hasTouch:mobile,isMobile:mobile,reducedMotion:'reduce'});
  const page=await context.newPage(),errors=[];
  page.on('pageerror',e=>errors.push(e.message));page.on('console',m=>{if(m.type()==='error')errors.push(m.text())});
  await page.goto(base,{waitUntil:'domcontentloaded'});await page.waitForSelector('#globe-canvas[data-ready="true"]');
  return {browser,page,errors};
}
async function focus(page,query,selector){
  await page.fill('#search',query);await page.locator(selector).click();
  await page.waitForFunction(()=>document.querySelector('#globe-canvas').dataset.lod==='high');
  return page.locator('#globe-canvas');
}
function yaw(rotation){return Number(rotation.split(',')[0]);}
async function dragTurns(page,canvas,count,vertical=false){
  const box=await canvas.boundingBox();
  for(let i=0;i<count;i++){
    const sx=box.x+box.width*.25,sy=box.y+box.height*.5;
    await page.mouse.move(sx,sy);await page.mouse.down();
    await page.mouse.move(vertical?sx:box.x+box.width*.75,vertical?box.y+box.height*.72:sy,{steps:8});await page.mouse.up();
  }
}
async function nonBackgroundPixels(canvas){return canvas.evaluate(c=>{const x=c.getContext('2d').getImageData(0,0,c.width,c.height).data;let n=0;for(let i=0;i<x.length;i+=4)if((x[i]===102&&x[i+1]===112&&x[i+2]===107)||(x[i]===35&&x[i+1]===122&&x[i+2]===78)||(x[i]===166&&x[i+1]===95&&x[i+2]===46))n++;return n})}

test('desktop supports successive full yaw rotations at overview and deep zoom',async()=>{const {browser,page,errors}=await open({width:1440,height:1000});try{
  const canvas=page.locator('#globe-canvas');let before=yaw(await canvas.getAttribute('data-rotation'));await dragTurns(page,canvas,4);let after=yaw(await canvas.getAttribute('data-rotation'));assert.ok(after-before>360,`overview yaw ${before} -> ${after}`);
  await focus(page,'Hawaii','[data-place="hawaii"]');assert.equal(await canvas.getAttribute('data-zoom'),'16.0000');assert.equal(await canvas.getAttribute('data-lod'),'high');assert.ok(await nonBackgroundPixels(canvas)>100,'Hawaiian geometry is painted');await canvas.screenshot({path:`${artifacts}/desktop-hawaii-high.png`});
  await canvas.scrollIntoViewIfNeeded();before=yaw(await canvas.getAttribute('data-rotation'));await dragTurns(page,canvas,12);after=yaw(await canvas.getAttribute('data-rotation'));assert.ok(after-before>360,`deep yaw ${before} -> ${after}`);assert.ok(await nonBackgroundPixels(canvas)>20,'land remains after repeated deep rotations');
  assert.deepEqual(errors,[]);await canvas.screenshot({path:`${artifacts}/desktop-after-deep-full-turns.png`});
}finally{await browser.close()}});

test('Hong Kong and Monaco switch from overview markers to real high-detail boundaries',async()=>{const {browser,page,errors}=await open({width:1440,height:1000});try{
  const canvas=await focus(page,'Hong Kong','[data-code="HK"]');assert.equal(await canvas.getAttribute('data-zoom'),'28.0000');assert.ok(await nonBackgroundPixels(canvas)>50);await canvas.screenshot({path:`${artifacts}/desktop-hong-kong-high.png`});
  await page.fill('#search','Monaco');await page.locator('[data-code="MC"]').click();await page.waitForFunction(()=>document.querySelector('#globe-canvas').dataset.zoom==='72.0000');assert.equal(await canvas.getAttribute('data-lod'),'high');assert.ok(await nonBackgroundPixels(canvas)>20);await canvas.screenshot({path:`${artifacts}/desktop-monaco-high.png`});
  await canvas.scrollIntoViewIfNeeded();await canvas.focus();await page.keyboard.press('ArrowRight');await page.keyboard.press('ArrowUp');await canvas.press('-');await page.waitForTimeout(40);assert.ok(Number(await canvas.getAttribute('data-zoom'))<72,'keyboard zoom works at finite cap');assert.deepEqual(errors,[]);
}finally{await browser.close()}});

for(const width of [320,390])test(`touch ${width}px pinches, deep vertical-drags, cancels cleanly and retains page routing at overview`,async()=>{const {browser,page,errors}=await open({width,height:844},true);try{
  const canvas=page.locator('#globe-canvas'),client=await page.context().newCDPSession(page),box=await canvas.boundingBox(),cx=box.x+box.width/2,cy=box.y+box.height/2;
  const pt=(x,y,id)=>({x,y,id,radiusX:5,radiusY:5,force:1});
  const overviewRotation=await canvas.getAttribute('data-rotation');await client.send('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[pt(cx,cy+55,1)]});for(let i=1;i<=8;i++)await client.send('Input.dispatchTouchEvent',{type:'touchMove',touchPoints:[pt(cx,cy+55-i*12,1)]});await client.send('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]});assert.equal(await canvas.getAttribute('data-rotation'),overviewRotation,'overview vertical gesture remains page scroll');
  await canvas.scrollIntoViewIfNeeded();const b=await canvas.boundingBox(),x=b.x+b.width/2,y=b.y+b.height/2;await client.send('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[pt(x-45,y,11),pt(x+45,y,12)]});for(let i=1;i<=14;i++)await client.send('Input.dispatchTouchEvent',{type:'touchMove',touchPoints:[pt(x-45-i*6,y,11),pt(x+45+i*6,y,12)]});await client.send('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]});assert.ok(Number(await canvas.getAttribute('data-zoom'))>2,'pinch zooms');
  const deepRotation=await canvas.getAttribute('data-rotation');await client.send('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[pt(x,y-50,21)]});for(let i=1;i<=10;i++)await client.send('Input.dispatchTouchEvent',{type:'touchMove',touchPoints:[pt(x,y-50+i*10,21)]});await client.send('Input.dispatchTouchEvent',{type:'touchCancel',touchPoints:[]});assert.notEqual(await canvas.getAttribute('data-rotation'),deepRotation,'deep vertical drag changes latitude');assert.ok(await nonBackgroundPixels(canvas)>20);assert.deepEqual(errors,[]);await canvas.screenshot({path:`${artifacts}/mobile-${width}-deep.png`});
}finally{await browser.close()}});
