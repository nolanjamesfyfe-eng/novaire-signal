import assert from 'node:assert/strict';
import fs from 'node:fs';
import {spawn} from 'node:child_process';
import playwright from '/root/.hermes/cache/scratch/health-qa/node_modules/playwright-core/index.js';
const root=new URL('..',import.meta.url).pathname,port=4319,tmp=root+'tests/.pw-camera-tmp';fs.mkdirSync(tmp,{recursive:true});process.env.TMPDIR=tmp;
const server=spawn('python3',['-m','http.server',String(port),'--bind','127.0.0.1'],{cwd:root,stdio:'ignore'});let browser;
const distance=state=>state.distance;
try{
 for(let i=0;i<100;i++){try{if((await fetch(`http://127.0.0.1:${port}/health/`)).ok)break}catch{}await new Promise(resolve=>setTimeout(resolve,100))}
 browser=await playwright.chromium.launch({headless:true,executablePath:'/snap/bin/chromium',args:['--no-sandbox']});
 const page=await browser.newPage({viewport:{width:1280,height:900}}),errors=[];page.on('pageerror',error=>errors.push(String(error)));
 await page.goto(`http://127.0.0.1:${port}/health/`,{waitUntil:'domcontentloaded',timeout:120000});await page.waitForFunction(()=>window.__HEALTH_ATLAS__?.ready===true,null,{timeout:180000});
 await page.locator('.view-controls [data-view="back"]').click();await page.waitForFunction(()=>!window.__HEALTH_ATLAS__.state.cameraTransitioning);
 const zoom=[];for(let i=0;i<4;i++){await page.locator('#zoom-in').click();zoom.push(distance(await page.evaluate(()=>window.__HEALTH_ATLAS__.state)))}assert.ok(zoom.every((value,index)=>!index||value<zoom[index-1]),`native zoom clicks were not monotonic: ${zoom}`);
 const beforeLayer=await page.evaluate(()=>window.__HEALTH_ATLAS__.state);await page.locator('[data-layer="bone"]').click();const bone=await page.evaluate(()=>window.__HEALTH_ATLAS__.state);assert.deepEqual(bone.camera,beforeLayer.camera);assert.deepEqual(bone.target,beforeLayer.target);await page.locator('[data-layer="skin"]').click();const skin=await page.evaluate(()=>window.__HEALTH_ATLAS__.state);assert.deepEqual(skin.camera,bone.camera);assert.deepEqual(skin.target,bone.target);
 const beforeResize=skin;await page.setViewportSize({width:900,height:720});await page.waitForTimeout(100);const resized=await page.evaluate(()=>window.__HEALTH_ATLAS__.state);assert.deepEqual(resized.target,beforeResize.target,'viewport resize must preserve orbit target');assert.ok(Math.abs(resized.azimuth-beforeResize.azimuth)<1e-9,'viewport resize must preserve azimuth');assert.ok(Math.abs(resized.polar-beforeResize.polar)<1e-9,'viewport resize must preserve polar angle');assert.deepEqual(errors,[]);
 console.log(JSON.stringify({ok:true,zoomDistances:zoom,layerCameraPreserved:true,resizeOrientationPreserved:true}));
}finally{if(browser)await browser.close();server.kill('SIGTERM')}
