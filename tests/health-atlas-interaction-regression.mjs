import assert from 'node:assert/strict';
import fs from 'node:fs';
import {spawn} from 'node:child_process';
import playwright from '/root/.hermes/cache/scratch/health-qa/node_modules/playwright-core/index.js';
const root=new URL('..',import.meta.url).pathname;
const out=process.env.HEALTH_INTERACTION_OUTPUT||'/root/.hermes/cache/scratch/evidence-health-hands/interaction';fs.mkdirSync(out,{recursive:true});process.env.TMPDIR=root+'tests/.pw-interaction-tmp';fs.mkdirSync(process.env.TMPDIR,{recursive:true});
const server=spawn('python3',['-m','http.server','4191','--bind','127.0.0.1'],{cwd:root,stdio:'ignore'});let browser;
const distance=s=>Math.hypot(...s.camera.map((v,i)=>v-s.target[i]));
for(let i=0;i<80;i++){try{if((await fetch('http://127.0.0.1:4191/health/')).ok)break}catch{}await new Promise(r=>setTimeout(r,100))}
try{
 browser=await playwright.chromium.launch({headless:true,executablePath:'/snap/bin/chromium',args:['--no-sandbox']});
 const report={};
 for(const cfg of [{name:'desktop',viewport:{width:1440,height:1000}},{name:'mobile',viewport:{width:390,height:844},hasTouch:true,isMobile:true}]){
  const page=await browser.newPage({...cfg,deviceScaleFactor:1});const errors=[];page.on('pageerror',e=>errors.push(String(e)));
  await page.goto('http://127.0.0.1:4191/health/',{waitUntil:'domcontentloaded',timeout:120000});await page.waitForFunction(()=>window.__HEALTH_ATLAS__?.ready===true,null,{timeout:120000});
  const canvas=page.locator('#atlas-canvas'),box=await canvas.boundingBox();const cycles=[];
  for(const layer of ['muscle','bone','skin']){
   await page.locator(`[data-layer="${layer}"]`).click();await page.evaluate(()=>window.__HEALTH_ATLAS__.view('front'));await page.waitForTimeout(150);const before=await page.evaluate(()=>window.__HEALTH_ATLAS__.state);
   for(let n=0;n<3;n++){await page.locator('#zoom-in').click();await page.waitForTimeout(400);await page.locator('#zoom-out').click();await page.waitForTimeout(400)}
   const afterButtons=await page.evaluate(()=>window.__HEALTH_ATLAS__.state);assert.ok(Number.isFinite(distance(afterButtons))&&distance(afterButtons)>=afterButtons.near&&distance(afterButtons)<=32,`${cfg.name}/${layer} repeated button zoom remains bounded`);
   await page.mouse.move(box.x+box.width*.5,box.y+box.height*.45);await page.mouse.wheel(0,-320);await page.waitForTimeout(300);const wheelIn=await page.evaluate(()=>window.__HEALTH_ATLAS__.state);assert.ok(distance(wheelIn)<distance(before),`${cfg.name}/${layer} wheel zoom in`);
   await page.mouse.wheel(0,320);await page.waitForTimeout(350);
   const start=await page.evaluate(()=>window.__HEALTH_ATLAS__.state),turns=[];for(let n=0;n<4;n++){await page.mouse.move(box.x+box.width*.72,box.y+box.height*.5);await page.mouse.down();await page.mouse.move(box.x+box.width*.28,box.y+box.height*.5,{steps:18});await page.mouse.up();await page.waitForTimeout(120);turns.push(await page.evaluate(()=>window.__HEALTH_ATLAS__.state))}const fullTurn=turns.at(-1);let travel=0,prior=start.azimuth;for(const state of turns){let delta=state.azimuth-prior;while(delta>Math.PI)delta-=Math.PI*2;while(delta<-Math.PI)delta+=Math.PI*2;travel+=Math.abs(delta);prior=state.azimuth}assert.ok(travel>Math.PI*1.5,`${cfg.name}/${layer} repeated drags must provide 360-capable azimuth travel, got ${travel}`);assert.equal(await page.evaluate(()=>window.__HEALTH_ATLAS__.selected),null,`${cfg.name}/${layer} drag must not select`);
   await page.mouse.move(box.x+box.width*.5,box.y+box.height*.68);await page.mouse.down();await page.mouse.move(box.x+box.width*.5,box.y+box.height*.30,{steps:16});await page.mouse.up();await page.waitForTimeout(200);const vertical=await page.evaluate(()=>window.__HEALTH_ATLAS__.state);assert.ok(Math.abs(vertical.camera[1]-fullTurn.camera[1])>1,`${cfg.name}/${layer} useful vertical orbit`);
   cycles.push({layer,start,fullTurn,vertical});await canvas.screenshot({path:`${out}/${cfg.name}-${layer}-oblique.png`});
  }
  const timing=await page.evaluate(async()=>{const samples=[];let last=performance.now();for(let i=0;i<90;i++)await new Promise(resolve=>requestAnimationFrame(now=>{samples.push(now-last);last=now;resolve()}));samples.sort((a,b)=>a-b);return{median:samples[45],p95:samples[Math.floor(samples.length*.95)],max:samples.at(-1)}});assert.ok(timing.p95<80,`${cfg.name} software-browser p95 frame interval ${timing.p95}`);
  if(cfg.name==='mobile'){
   const client=await page.context().newCDPSession(page);const cx=box.x+box.width/2,cy=box.y+box.height/2;
   const pre=await page.evaluate(()=>window.__HEALTH_ATLAS__.state);await client.send('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[{x:cx-35,y:cy,id:1},{x:cx+35,y:cy,id:2}]});for(let i=1;i<=8;i++)await client.send('Input.dispatchTouchEvent',{type:'touchMove',touchPoints:[{x:cx-35-i*5,y:cy,id:1},{x:cx+35+i*5,y:cy,id:2}]});await client.send('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]});await page.waitForTimeout(350);const post=await page.evaluate(()=>window.__HEALTH_ATLAS__.state);assert.ok(distance(post)<distance(pre),'mobile pinch-out must zoom in without jump');
   await page.setViewportSize({width:844,height:390});await page.waitForTimeout(350);const frame=await page.evaluate(()=>window.__HEALTH_ATLAS__.figureFrame());assert.ok(Number.isFinite(frame.left)&&frame.right>frame.left,'orientation resize keeps valid projection');
  }
  assert.deepEqual(errors,[]);report[cfg.name]={timing,cycles:cycles.map(x=>({layer:x.layer,startDistance:distance(x.start),endDistance:distance(x.vertical)}))};await page.close();
 }
 fs.writeFileSync(`${out}/interaction-report.json`,JSON.stringify(report,null,2));console.log(JSON.stringify(report,null,2));console.log(`PASS health atlas interaction regression; evidence=${out}`);
}finally{if(browser)await browser.close();server.kill('SIGTERM')}
