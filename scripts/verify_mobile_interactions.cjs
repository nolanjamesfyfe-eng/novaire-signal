const {chromium}=require('/root/clawd/novaire-operations-system/node_modules/playwright');
const fs=require('fs'),assert=require('assert/strict');
const base=process.env.SIGNAL_BASE_URL||'http://127.0.0.1:18793/';
const out=process.env.EVIDENCE_DIR||process.env.TMPDIR+'/mobile-interactions';
(async()=>{
fs.mkdirSync(out,{recursive:true});const browser=await chromium.launch({executablePath:'/opt/google/chrome/chrome',args:['--no-sandbox']});
try{for(const width of [412,980]){
 const context=await browser.newContext({viewport:{width,height:width===980?2196:923},hasTouch:true,isMobile:true,deviceScaleFactor:2.625});
 if(process.env.SIGNAL_AUTH==='1'){const pin=fs.readFileSync('/root/clawd/.secrets','utf8').match(/^NOS_ACCESS_PIN=(.*)$/m)[1].trim().replace(/^['"]|['"]$/g,'');assert((await context.request.post(base+'api/portfolio-auth',{data:{pin}})).ok());}
 const page=await context.newPage();
 await page.goto(base+'portfolio/finances/');await page.evaluate(()=>document.fonts.ready);
 const canvas=page.locator('#chart');await canvas.waitFor();await page.waitForTimeout(500);
 const initial=await canvas.boundingBox();assert(initial.width<=width&&initial.height>200);
 for(const tab of await page.locator('.tab').all()){await tab.tap();assert.equal(await tab.getAttribute('aria-selected'),'true');}
 await page.waitForTimeout(300);const final=await canvas.boundingBox();assert.equal(final.width,initial.width,'canvas cannot grow intrinsically after redraw');assert.equal(await page.evaluate(()=>innerWidth),width);
 await page.screenshot({path:`${out}/finances-${width}.png`,scale:'css'});
 await page.goto(base+'portfolio/');
 await page.locator('.holdings-toggle').tap();
 const cells=page.locator('.portfolio-table td');assert(await cells.count()>0);
 assert(await cells.first().isVisible(),'holdings actually open');
 assert(await cells.first().evaluate(e=>parseFloat(getComputedStyle(e).fontSize))>=13);
 assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'opened holdings do not shrink viewport');
 await cells.first().scrollIntoViewIfNeeded();await page.screenshot({path:`${out}/holdings-${width}.png`,scale:'css'});
 await page.goto(base+(base.includes('127.0.0.1')?'map/':'flaneur'));await page.waitForSelector('#globe-canvas[data-ready=true]');
 const globe=page.locator('#globe-canvas');await globe.scrollIntoViewIfNeeded();let box=await globe.boundingBox();const x=box.x+box.width/2,y=box.y+box.height/2;
 await page.touchscreen.tap(x,y);assert.match(await page.locator('.tooltip.show').innerText(),/Capital:.*[\s\S]*Population:.*[\s\S]*GDP:/);
 const client=await context.newCDPSession(page),point=(x,y,id)=>({x,y,id,radiusX:5,radiusY:5,force:1});
 const before=await globe.evaluate(e=>e.toDataURL());
 await client.send('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[point(x-70,y,1)]});
 for(let i=1;i<=12;i++){await client.send('Input.dispatchTouchEvent',{type:'touchMove',touchPoints:[point(x-70+i*10,y,1)]});await page.waitForTimeout(20);}
 await client.send('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]});await page.waitForTimeout(100);
 assert.notEqual(await globe.evaluate(e=>e.toDataURL()),before,'trusted drag rotates painted globe');
 await page.touchscreen.tap(x,y);assert(await page.locator('.tooltip.show').count());
 await client.send('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[point(x-50,y,2),point(x+50,y,3)]});
 for(let i=1;i<=8;i++)await client.send('Input.dispatchTouchEvent',{type:'touchMove',touchPoints:[point(x-50-i*5,y,2),point(x+50+i*5,y,3)]});
 await client.send('Input.dispatchTouchEvent',{type:'touchCancel',touchPoints:[]});await page.waitForTimeout(100);
 await page.touchscreen.tap(x,y);assert(await page.locator('.tooltip.show').count(),'tap after pinch/cancel');
 await page.screenshot({path:`${out}/globe-${width}.png`,scale:'css'});
 console.log(`PASS ${width}: finance tabs/stable canvas, open readable holdings, native globe tap/drag/pinch/cancel/re-tap`);
 await context.close();
}}finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
