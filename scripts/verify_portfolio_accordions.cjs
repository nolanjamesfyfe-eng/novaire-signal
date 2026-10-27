// Exercise every account, not only the primary holdings table, using native touch.
const {chromium}=require('/root/clawd/novaire-operations-system/node_modules/playwright');
const fs=require('fs'),assert=require('assert/strict');
const base=process.env.SIGNAL_BASE_URL||'http://127.0.0.1:18793/';
const out=process.env.EVIDENCE_DIR||process.env.TMPDIR+'/portfolio-accordions';
(async()=>{
 fs.mkdirSync(out,{recursive:true});
 const browser=await chromium.launch({executablePath:'/opt/google/chrome/chrome',args:['--no-sandbox']});const results=[];
 try{for(const width of [412,980]){
  const context=await browser.newContext({viewport:{width,height:width===980?2196:923},hasTouch:true,isMobile:true,deviceScaleFactor:2.625});
  if(process.env.SIGNAL_AUTH==='1'){const pin=fs.readFileSync('/root/clawd/.secrets','utf8').match(/^NOS_ACCESS_PIN=(.*)$/m)[1].trim().replace(/^['"]|['"]$/g,'');assert((await context.request.post(base+'api/portfolio-auth',{data:{pin}})).ok());}
  const page=await context.newPage();await page.goto(base+'portfolio/');await page.evaluate(()=>document.fonts.ready);
  const toggles=page.locator('.collapse-toggle');assert.equal(await toggles.count(),4,'all four current account accordions covered');
  for(let i=0;i<await toggles.count();i++){
   const toggle=toggles.nth(i),label=await toggle.innerText();
   await toggle.tap({timeout:5000});
   const geometry=await toggle.evaluate(t=>{const c=t.nextElementSibling,r=c.getBoundingClientRect();return {label:t.textContent.trim(),visible:getComputedStyle(c).display!=='none',innerWidth,documentWidth:document.documentElement.scrollWidth,viewportWidth:visualViewport.width,left:r.left,right:r.right,scrollWidth:c.scrollWidth,clientWidth:c.clientWidth,overflow:getComputedStyle(c).overflowX,rows:c.querySelectorAll('tr').length};});
   results.push({width,...geometry});fs.writeFileSync(out+'/results.json',JSON.stringify(results,null,2));
   assert(geometry.visible&&geometry.rows>0,`${label}: actual account rows open`);
   assert.equal(geometry.innerWidth,width,`${label}: must not enlarge mobile layout viewport`);
   assert(geometry.documentWidth<=width,`${label}: must not overflow document`);
   assert(geometry.left>=0&&geometry.right<=width+1,`${label}: content stays inside screen`);
   const content=toggle.locator('xpath=following-sibling::*[1]');
   await content.evaluate(e=>{e.scrollLeft=e.scrollWidth;});
   assert(await content.evaluate(e=>e.scrollWidth-e.clientWidth-e.scrollLeft<=1),`${label}: last columns reachable`);
   await content.evaluate(e=>{e.scrollLeft=0;});
   await toggle.scrollIntoViewIfNeeded();await page.screenshot({path:`${out}/account-${width}-${i}.png`,scale:'css'});
   // Leave all preceding accounts open: this is the state that broke Alpaca taps.
  }
  for(let i=3;i>=0;i--){const t=toggles.nth(i);await t.tap({timeout:5000});assert(await t.evaluate(e=>getComputedStyle(e.nextElementSibling).display==='none'));await t.tap({timeout:5000});assert(await t.evaluate(e=>getComputedStyle(e.nextElementSibling).display!=='none'));}
  console.log(`PASS ${width}: all four accounts open/close/reopen, no viewport expansion, final columns reachable`);await context.close();
 }}finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
