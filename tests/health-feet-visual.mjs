import playwright from '/root/.hermes/cache/scratch/health-qa/node_modules/playwright-core/index.js';
import { spawn } from 'node:child_process';
import fs from 'node:fs';
const root=new URL('..',import.meta.url).pathname;
const out=root+'tests/visual-fix';fs.mkdirSync(out,{recursive:true});
const server=spawn('python3',['-m','http.server','4182','--bind','127.0.0.1'],{cwd:root,stdio:'ignore'});
await new Promise(r=>setTimeout(r,700));
let browser;
try {
 browser=await playwright.chromium.launch({headless:true,executablePath:'/snap/bin/chromium',args:['--no-sandbox']});
 for (const cfg of [{name:'desktop',width:1440,height:1000},{name:'mobile',width:390,height:844}]) {
  const page=await browser.newPage({viewport:{width:cfg.width,height:cfg.height},deviceScaleFactor:1});
  await page.goto('http://127.0.0.1:4182/health/',{waitUntil:'domcontentloaded',timeout:120000});
  await page.waitForFunction(()=>window.__HEALTH_ATLAS__?.ready===true,null,{timeout:120000});
  const canvas=page.locator('#atlas-canvas');
  await canvas.screenshot({path:`${out}/feet-${cfg.name}-front.png`});
  const box=await canvas.boundingBox();
  await page.mouse.move(box.x+box.width*.52,box.y+box.height*.48);await page.mouse.down();await page.mouse.move(box.x+box.width*.66,box.y+box.height*.49,{steps:12});await page.mouse.up();await page.waitForTimeout(500);
  await canvas.screenshot({path:`${out}/feet-${cfg.name}-three-quarter.png`});
  await page.close();
 }
 console.log('PASS foot visual captures: desktop/mobile front + three-quarter');
} finally {if(browser)await browser.close();server.kill('SIGTERM')}
