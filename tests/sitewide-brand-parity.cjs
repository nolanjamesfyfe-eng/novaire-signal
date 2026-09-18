const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const {chromium}=require('/root/clawd/novaire-operations-system/node_modules/playwright');
const ROOT=path.resolve(__dirname,'..');
const SITE_URL=process.env.SITE_URL||'http://127.0.0.1:8765';
const routes=[
  ['/', 'index.html'],
  ['/flaneur','map/index.html'],
  ['/portfolio-lock.html','portfolio-lock.html'],
  ['/portfolio/','portfolio/index.html'],
  ['/portfolio/daily/','portfolio/daily/index.html'],
  ['/portfolio/evolutionfund/','portfolio/evolutionfund/index.html'],
];

test('public and authenticated route artifacts carry two canonical functional brands',()=>{
  for(const [route,file] of routes){
    const html=fs.readFileSync(path.join(ROOT,file),'utf8');
    assert.ok((html.match(/class="[^"]*signal-brand-row[^"]*"/g)||[]).length>=2,`${route} top and bottom brand`);
    assert.ok((html.match(/href="\/flaneur" class="signal-map"/g)||[]).length>=2,`${route} globe links`);
    assert.ok((html.match(/href="\/" class="signal-wordmark"/g)||[]).length>=2,`${route} wordmark links`);
    assert.ok((html.match(/href="\/portfolio\/" class="signal-bolt"/g)||[]).length>=2,`${route} bolt links`);
    assert.ok((html.match(/viewBox="45 38 200 264"/g)||[]).length>=2,`${route} traced bolt`);
  }
});

test('brand computed geometry, typography and antique gold match desktop and mobile',async()=>{
 const browser=await chromium.launch({headless:true,executablePath:'/snap/bin/chromium',args:['--no-sandbox']});
 try{
  for(const viewport of [{width:1280,height:900},{width:390,height:844}]){
   for(const [route,file] of routes){
    const page=await browser.newPage({viewport});
    await page.goto(SITE_URL+(SITE_URL.includes('127.0.0.1')?'/'+file:route),{waitUntil:'domcontentloaded'});
    const rows=await page.locator('.signal-brand-row').evaluateAll(nodes=>nodes.slice(0,2).map(n=>{
      const r=n.getBoundingClientRect(),w=n.querySelector('.signal-wordmark'),s=w.querySelector('span'),g=n.querySelector('.signal-map'),b=n.querySelector('.signal-bolt');
      return {width:r.width,height:r.height,gap:getComputedStyle(n).gap,center:r.left+r.width/2,containerCenter:(n.parentElement.getBoundingClientRect().left+n.parentElement.getBoundingClientRect().right)/2,viewport:innerWidth,wordmark:{color:getComputedStyle(w).color,fontStyle:getComputedStyle(w).fontStyle},signal:{color:getComputedStyle(s).color,fontStyle:getComputedStyle(s).fontStyle},globe:getComputedStyle(g).color,bolt:getComputedStyle(b).color,links:[g.getAttribute('href'),w.getAttribute('href'),b.getAttribute('href')]};
    }));
    assert.equal(rows.length,2,`${route} ${viewport.width}`);
    for(const row of rows){
      assert.equal(row.gap,'12px'); assert.deepEqual(row.links,['/flaneur','/','/portfolio/']);
      assert.equal(row.wordmark.fontStyle,'normal'); assert.equal(row.signal.fontStyle,'italic');
      assert.equal(row.signal.color,'rgb(181, 150, 98)'); assert.equal(row.globe,'rgb(181, 150, 98)'); assert.equal(row.bolt,'rgb(181, 150, 98)');
      assert.ok(Math.abs(row.containerCenter-row.viewport/2)<2,`${route} brand container centered at ${viewport.width}: ${JSON.stringify(row)}`);
    }
    assert.ok(Math.abs(rows[0].width-rows[1].width)<1 && Math.abs(rows[0].height-rows[1].height)<1,`${route} same top/bottom size`);
    await page.close();
   }
  }
 }finally{await browser.close()}
});
