const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const http = require('node:http');
const {chromium} = require('/root/clawd/novaire-operations-system/node_modules/playwright');
const root = path.resolve(__dirname,'..');
const out = process.env.OUT || '/root/.hermes/cache/scratch/signal-x-gray-local';
fs.mkdirSync(out,{recursive:true});
const server = http.createServer((req,res)=>{
 const p=new URL(req.url,'http://localhost').pathname;
 const file=path.join(root,p==='/'?'index.html':p);
 if(!fs.existsSync(file)||fs.statSync(file).isDirectory()){res.writeHead(404);return res.end();}
 res.setHeader('Content-Type',file.endsWith('.json')?'application/json':file.endsWith('.html')?'text/html':'application/octet-stream');
 res.end(fs.readFileSync(file));
});
(async()=>{
 await new Promise(r=>server.listen(0,'127.0.0.1',r));
 const browser=await chromium.launch({headless:true,executablePath:'/opt/google/chrome/chrome',args:['--no-sandbox']});
 const results=[];
 try {
 for(const width of [1440,390,360]){
  const page=await browser.newPage({viewport:{width,height:1000},reducedMotion:'reduce'});
  await page.goto(process.env.URL || `http://127.0.0.1:${server.address().port}/`);
  await page.waitForSelector('#signal-feed .feed-text',{state:'attached'});
  await page.evaluate(()=>{document.querySelector('#signal-feed-card').open=true;document.querySelector('#zerohedge-card')?.setAttribute('open','');});
  await page.evaluate(()=>document.fonts.ready);
  for(const phase of ['initial','refreshed']){
   if(phase==='refreshed'){await page.evaluate(()=>refreshSignals(true));}
   await page.locator('#signal-feed-card').scrollIntoViewIfNeeded();
   const result=await page.evaluate(()=>{
    const texts=[...document.querySelectorAll('#signal-feed .feed-text')];
    const zh=getComputedStyle(document.querySelector('#zerohedge-feed .feed-card-excerpt')).color;
    const nodes=[...document.querySelectorAll('#signal-feed-card, #signal-feed-card *')];
    const snapshot=()=>nodes.map(el=>{const s=getComputedStyle(el),r=el.getBoundingClientRect();return {text:el.textContent,href:el.getAttribute('href'),style:Object.fromEntries([...s].filter(k=>!(el.matches('.feed-text') && (k==='color'||k.endsWith('-color')))&&!k.startsWith('--')).map(k=>[k,s.getPropertyValue(k)])),rect:[r.x,r.y,r.width,r.height]};});
    const actual=snapshot();
    const colors=texts.map(e=>getComputedStyle(e).color);
    const override=document.createElement('style');override.textContent='#signal-feed .feed-text{color:var(--text)!important}';document.head.append(override);
    const before=snapshot();override.remove();
    return {zh,colors,actual,before,count:texts.length,overflow:document.documentElement.scrollWidth>innerWidth};
   });
   assert.equal(result.count,3);assert.ok(result.colors.every(c=>c===result.zh));assert.equal(result.zh,'rgb(168, 164, 186)');
   assert.deepEqual(result.actual,result.before,'Color change must preserve every other computed style, content, link and rectangle');
   assert.equal(result.overflow,false);
   delete result.actual;delete result.before;
   results.push({width,phase,...result});
   await page.locator('#signal-feed-card').screenshot({path:path.join(out,`${width}-${phase}.png`)});
  }
  await page.locator('#signal-feed-card > summary').click();
  await page.waitForTimeout(150);
  await page.reload();
  await page.waitForSelector('#signal-feed .feed-text',{state:'attached'});
  assert.equal(await page.locator('#signal-feed-card').evaluate(e=>e.open),false,'Collapsed preference survives reload');
  await page.close();
 }
 fs.writeFileSync(path.join(out,'results.json'),JSON.stringify(results,null,2));console.log(JSON.stringify(results));
 } finally {await browser.close();server.close();}
})().catch(e=>{console.error(e);server.close();process.exitCode=1;});
