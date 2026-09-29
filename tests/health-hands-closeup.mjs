import playwright from '/root/.hermes/cache/scratch/health-qa/node_modules/playwright-core/index.js';
import {spawn} from 'node:child_process';
import {strict as assert} from 'node:assert';
import fs from 'node:fs';
const {chromium}=playwright,root=new URL('..',import.meta.url).pathname;
const out=process.env.HAND_QA_OUTPUT||'/root/.hermes/cache/scratch/output/health-intact-hands';fs.mkdirSync(out,{recursive:true});
const tmp=root+'tests/.pw-hands-tmp';fs.mkdirSync(tmp,{recursive:true});process.env.TMPDIR=tmp;
const server=spawn('python3',['-m','http.server','4191','--bind','127.0.0.1'],{cwd:root,stdio:'ignore'});await new Promise(r=>setTimeout(r,800));
let browser;
try{
 browser=await chromium.launch({headless:true,executablePath:'/snap/bin/chromium',args:['--no-sandbox','--use-gl=swiftshader']});
 const page=await browser.newPage({viewport:{width:1000,height:760},deviceScaleFactor:1});const errors=[];page.on('pageerror',e=>errors.push(String(e)));
 await page.goto('http://127.0.0.1:4191/health/',{waitUntil:'domcontentloaded',timeout:120000});await page.waitForFunction(()=>window.__HEALTH_ATLAS__?.ready===true,null,{timeout:120000});
 const metrics=await page.evaluate(()=>window.__HEALTH_ATLAS__.handMetrics);assert.equal(metrics.totalMeshes,54);for(const side of ['left','right']){assert.equal(metrics.sides[side].carpals,8);assert.equal(metrics.sides[side].meshes,27);assert.deepEqual(metrics.sides[side].digits.map(x=>x.segments),[3,4,4,4,4]);assert.ok(metrics.sides[side].maximumJointGap<.01,`${side} joint gap ${metrics.sides[side].maximumJointGap}`);assert.ok(metrics.sides[side].digits.every(x=>x.jointGaps.every(g=>g<.01)))}
 await page.evaluate(()=>window.__HEALTH_ATLAS__.setLayer('bone'));await page.waitForTimeout(500);
 async function focus(side,view){assert.equal(await page.evaluate(([s,v])=>window.__HEALTH_ATLAS__.focusHand(s,v),[side,view]),true);await page.waitForTimeout(350)}
 async function shot(name){const clip=await page.locator('#atlas-canvas').boundingBox();await page.screenshot({path:`${out}/${name}.png`,clip,animations:'disabled',timeout:120000})}
 async function drag(dx,dy){const b=await page.locator('#atlas-canvas').boundingBox();await page.mouse.move(b.x+b.width*.5,b.y+b.height*.5);await page.mouse.down();await page.mouse.move(b.x+b.width*.5+dx,b.y+b.height*.5+dy,{steps:18});await page.mouse.up();await page.waitForTimeout(500)}
 for(const side of ['left','right'])for(const view of ['palm','palmar-oblique','dorsal-oblique','dorsal']){await focus(side,view);await shot(`${side}-${view}`)}
 for(const weight of [65,110]){await page.evaluate(w=>{const x=document.querySelector('input[data-physique="weight"]');x.value=String(w);x.dispatchEvent(new Event('input',{bubbles:true}))},weight);await focus('left','palmar-oblique');await shot(`left-weight-${weight}`)}
 assert.equal(errors.length,0,errors.join('\n'));fs.writeFileSync(`${out}/metrics.json`,JSON.stringify({metrics,errors,captures:fs.readdirSync(out).filter(x=>x.endsWith('.png')).sort()},null,2));
 console.log(`PASS replacement hands: ${metrics.totalMeshes} meshes; bilateral 8 carpals + 5 complete digit rays; 10 close-up captures; 0 browser errors; ${out}`);
}finally{if(browser)await browser.close();server.kill('SIGTERM')}
