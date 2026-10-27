const {chromium}=require('/root/clawd/novaire-operations-system/node_modules/playwright');
const fs=require('fs');
const assert=require('node:assert/strict');
const path=require('path');
const OUT=process.env.QA_OUTPUT_DIR||'/root/.hermes/cache/scratch';
const phase=process.env.QA_PHASE||'live';
(async()=>{
 fs.mkdirSync(OUT,{recursive:true});
 const browser=await chromium.launch({headless:true,executablePath:process.env.CHROMIUM_PATH||'/usr/bin/google-chrome',args:['--no-sandbox']});
 const results=[];
 try {
 for(const width of [1440,390,360]) {
  const page=await browser.newPage({viewport:{width,height:1000}});
  await page.goto(process.env.QA_URL||'https://novairesignal.com',{waitUntil:'domcontentloaded'});
  await page.locator('#thailand-news-card').evaluate(e=>e.open=true);
  await page.locator('#thailand-news-card').scrollIntoViewIfNeeded();
  for(const card of await page.locator('.thai-feed-card').all()) {
   await card.evaluate(e=>e.scrollIntoView({block:'center',inline:'center'}));
   await card.locator('.feed-card-source').click({trial:true});
   await card.evaluate(async e=>{await Promise.all([...e.querySelectorAll('img')].map(i=>i.decode().catch(()=>{})))});
  }
  await page.locator('#thai-news-feed .feed-card-grid').evaluate(e=>e.scrollLeft=0);
  await page.waitForTimeout(500);
  const data=await page.evaluate(()=>{
   const rect=e=>{const r=e.getBoundingClientRect();return {x:r.x,y:r.y,width:r.width,height:r.height,bottom:r.bottom,right:r.right}};
   const cards=sel=>[...document.querySelectorAll(sel)].map(e=>{
    const t=e.querySelector('.feed-card-title'),x=e.querySelector('.feed-card-excerpt'),f=e.querySelector('.feed-card-source');
    return {rect:rect(e),title:t.textContent,fullTitle:t.title,ariaLabel:t.getAttribute('aria-label'),excerpt:x?.textContent||'',href:f.href,footer:rect(f),body:rect(e.querySelector('.feed-card-body')),image:e.querySelector('img')?.naturalWidth||0,imageURL:e.querySelector('img')?.src||null,published:e.dataset.publishedAt,clamps:[getComputedStyle(t).webkitLineClamp,x?getComputedStyle(x).webkitLineClamp:null],font:getComputedStyle(t).fontSize,thumb:e.querySelector('img')?rect(e.querySelector('img')):null};
   });
   return {thai:cards('.thai-feed-card'),zh:cards('#zerohedge-feed .zh-feed-card'),thaiOuter:rect(document.querySelector('#thailand-news-card')),thaiGrid:rect(document.querySelector('#thai-news-feed')),zhGrid:rect(document.querySelector('#zerohedge-feed')),snap:getComputedStyle(document.querySelector('#thai-news-feed .feed-card-grid')).scrollSnapType};
  });
  assert.equal(data.thai.length,3,'three real Thailand cards');
  assert.equal(new Set(data.thai.map(x=>x.href)).size,3,'unique destinations');
  for(const item of data.thai){
   assert.ok(Math.abs(item.rect.height-data.zh[0].rect.height)<1,'peer height');
   assert.ok(Math.abs(item.rect.width-data.zh[0].rect.width)<1,'peer width');
   assert.equal(item.font,data.zh[0].font,'peer title typography');
   assert.deepEqual(item.clamps,width<620?['2','1']:['4','5']);
   assert.ok(item.footer.y>=item.body.bottom-0.5 && item.footer.bottom<=item.rect.bottom+0.5,'pinned footer fully inside');
   assert.ok(item.footer.right<=item.rect.right+0.5,'footer width');
   assert.ok([...item.title].length<=110 && [...item.excerpt].length<=140,'word-safe copy budget');
   assert.equal(item.fullTitle,item.ariaLabel,'full accessible title');
   assert.ok(item.published && !Number.isNaN(Date.parse(item.published)),'honest publication timestamp');
   if(process.env.QA_REQUIRE_IMAGES==='1') assert.ok(item.image>0,'real publisher thumbnail loaded');
  }
  assert.equal(data.snap,width<620?'x mandatory':'none');
  if(width>=620) assert.ok(data.thai.every(x=>Math.abs(x.rect.y-data.thai[0].rect.y)<1),'equal three-column row');
  // Source image failures must not collapse the shell or lose the footer.
  await page.locator('.thai-feed-card').first().evaluate(e=>{const img=e.querySelector('img');if(img)img.dispatchEvent(new Event('error'))});
  assert.equal(await page.locator('.thai-feed-card').first().locator('img').count(),0);
  const fallbackHeight=await page.locator('.thai-feed-card').first().evaluate(e=>e.getBoundingClientRect().height);
  assert.ok(Math.abs(fallbackHeight-data.thai[0].rect.height)<1);
  // Reload so evidence screenshots show the real, unmodified production cards.
  await page.reload({waitUntil:'domcontentloaded'});
  await page.locator('#thailand-news-card').evaluate(e=>e.open=true);
  await page.locator('#thailand-news-card').scrollIntoViewIfNeeded();
  await page.waitForTimeout(1500);
  await page.locator('#thailand-news-card').screenshot({path:path.join(OUT,`thai-${phase}-${width}.png`)});
  results.push({width,...data}); await page.close();
 }
 }finally{await browser.close()}
 fs.writeFileSync(path.join(OUT,`thai-${phase}.json`),JSON.stringify(results,null,2));
 console.log(JSON.stringify({ok:true,phase,results},null,2));
})().catch(e=>{console.error(e);process.exit(1)});
