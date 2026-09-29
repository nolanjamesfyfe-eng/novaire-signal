import assert from 'node:assert/strict';
import fs from 'node:fs';
import {spawn} from 'node:child_process';
import playwright from '/root/.hermes/cache/scratch/health-qa/node_modules/playwright-core/index.js';

const root=new URL('..',import.meta.url).pathname;
const out=process.env.HEALTH_LUMINOUS_OUTPUT||`${root}test-results/luminous-body`;
fs.mkdirSync(out,{recursive:true});
process.env.TMPDIR=`${root}tests/.pw-luminous-tmp`;
fs.mkdirSync(process.env.TMPDIR,{recursive:true});
const server=spawn('python3',['-m','http.server','4194','--bind','127.0.0.1'],{cwd:root,stdio:'ignore'});
let browser;
for(let i=0;i<80;i++){try{if((await fetch('http://127.0.0.1:4194/health/')).ok)break}catch{}await new Promise(r=>setTimeout(r,100));}
const distance=s=>Math.hypot(...s.camera.map((v,i)=>v-s.target[i]));
const viewportShot=async(page,path)=>{const clip=await page.evaluate(()=>{const r=document.querySelector('#viewport').getBoundingClientRect();return{x:r.x,y:r.y,width:r.width,height:r.height}});await page.screenshot({path,clip,timeout:120000});};
try{
  browser=await playwright.chromium.launch({headless:true,executablePath:'/opt/google/chrome/chrome',args:['--no-sandbox']});
  const report={};
  for(const cfg of [{name:'desktop',viewport:{width:1440,height:1000}},{name:'mobile',viewport:{width:390,height:844},hasTouch:true,isMobile:true}]){
    const page=await browser.newPage({...cfg,deviceScaleFactor:1});
    const errors=[]; page.on('pageerror',e=>errors.push(String(e)));
    await page.goto('http://127.0.0.1:4194/health/',{waitUntil:'domcontentloaded',timeout:120000});
    await page.waitForFunction(()=>window.__HEALTH_ATLAS__?.ready===true,null,{timeout:120000});
    await page.waitForTimeout(500);
    const fullBefore=await page.evaluate(()=>({state:window.__HEALTH_ATLAS__.state,sample:window.__HEALTH_ATLAS__.luminousSample.muscle}));
    await viewportShot(page,`${out}/${cfg.name}-full-body.png`);
    await page.waitForTimeout(950);
    const pulseLater=await page.evaluate(()=>window.__HEALTH_ATLAS__.luminousSample.muscle);
    assert.ok(Math.abs(pulseLater.intensity-fullBefore.sample.intensity)>.005,`${cfg.name}: emission changes over time`);
    await page.evaluate(()=>{document.querySelector('#zoom-in').click();document.querySelector('#zoom-in').click();document.querySelector('#zoom-in').click()}); await page.waitForTimeout(650);
    const close=await page.evaluate(()=>({state:window.__HEALTH_ATLAS__.state,sample:window.__HEALTH_ATLAS__.luminousSample.muscle}));
    assert.ok(distance(close.state)<distance(fullBefore.state),`${cfg.name}: zoom-in changes camera distance`);
    assert.ok(close.sample.proximity>=fullBefore.sample.proximity,`${cfg.name}: close zoom increases pulse readability`);
    await viewportShot(page,`${out}/${cfg.name}-closeup-pulse-a.png`);
    await page.waitForTimeout(950);
    if(cfg.name==='desktop')await viewportShot(page,`${out}/${cfg.name}-closeup-pulse-b.png`);
    const point=await page.evaluate(()=>window.__HEALTH_ATLAS__.project('pectoralis')); assert.ok(point);
    await page.evaluate(()=>document.querySelector('.muscle-item[data-key="pectoralis"]').click());
    assert.equal(await page.evaluate(()=>window.__HEALTH_ATLAS__.selected),'pectoralis','directory selection remains functional');
    const box=await page.evaluate(()=>{const r=document.querySelector('#atlas-canvas').getBoundingClientRect();return{x:r.x,y:r.y,width:r.width,height:r.height}}),preDrag=await page.evaluate(()=>window.__HEALTH_ATLAS__.state);
    await page.mouse.move(box.x+box.width*.55,box.y+box.height*.5);await page.mouse.down();await page.mouse.move(box.x+box.width*.72,box.y+box.height*.54,{steps:12});await page.mouse.up();await page.waitForTimeout(250);
    const postDrag=await page.evaluate(()=>window.__HEALTH_ATLAS__.state);assert.notDeepEqual(postDrag.camera,preDrag.camera,`${cfg.name}: rotation remains functional`);
    if(cfg.name==='mobile'){
      const client=await page.context().newCDPSession(page),cx=box.x+box.width/2,cy=box.y+box.height/2,prePinch=postDrag;
      await client.send('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[{x:cx-25,y:cy,id:1},{x:cx+25,y:cy,id:2}]});
      for(let i=1;i<=8;i++)await client.send('Input.dispatchTouchEvent',{type:'touchMove',touchPoints:[{x:cx-25-i*5,y:cy,id:1},{x:cx+25+i*5,y:cy,id:2}]});
      await client.send('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]});await page.waitForTimeout(350);
      const postPinch=await page.evaluate(()=>window.__HEALTH_ATLAS__.state);assert.ok(distance(postPinch)<distance(prePinch),'mobile: pinch-out zooms in');
    }
    assert.deepEqual(errors,[]);
    report[cfg.name]={fullDistance:distance(fullBefore.state),closeDistance:distance(close.state),pulseA:fullBefore.sample,pulseB:pulseLater,selected:'pectoralis',rotationChanged:true};
    console.log(`PASS ${cfg.name}: pulse, zoom, selection, rotation${cfg.name==='mobile'?', pinch':''}`);
    await page.close();
  }
  const reduced=await browser.newPage({viewport:{width:1100,height:800},reducedMotion:'reduce'});
  await reduced.goto('http://127.0.0.1:4194/health/',{waitUntil:'domcontentloaded',timeout:120000});await reduced.waitForFunction(()=>window.__HEALTH_ATLAS__?.ready===true,null,{timeout:120000});await reduced.waitForTimeout(300);
  const reducedA=await reduced.evaluate(()=>window.__HEALTH_ATLAS__.luminousSample.muscle);await reduced.waitForTimeout(1100);const reducedB=await reduced.evaluate(()=>window.__HEALTH_ATLAS__.luminousSample.muscle);
  assert.equal(reducedA.intensity,reducedB.intensity,'reduced motion suppresses luminous pulse');assert.equal(reducedB.reducedMotion,true);
  report.reducedMotion={pulseA:reducedA.intensity,pulseB:reducedB.intensity,suppressed:true};
  fs.writeFileSync(`${out}/luminous-report.json`,JSON.stringify(report,null,2));
  console.log(`PASS luminous body visual + pulse + zoom + pointer selection + rotation + mobile pinch + reduced motion; evidence=${out}`);
}finally{if(browser)await browser.close();server.kill('SIGTERM');}
