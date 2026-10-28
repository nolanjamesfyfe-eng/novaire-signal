const {chromium}=require('/root/clawd/novaire-operations-system/node_modules/playwright');
const fs=require('node:fs');const assert=require('node:assert/strict');
const base=process.env.BASE_URL||'https://novairesignal.com';
const out=process.env.QA_OUT||'/root/.hermes/cache/scratch/feed-live';fs.mkdirSync(out,{recursive:true});
(async()=>{
 const browser=await chromium.launch({executablePath:'/usr/bin/google-chrome',args:['--no-sandbox']});
 const results=[];
 try{
 for(const width of [1440,390,360]){
 const context=await browser.newContext({viewport:{width,height:1000}});const page=await context.newPage();
 await page.addInitScript(()=>{localStorage.setItem('nv_zerohedge_state','open');localStorage.setItem('nv_signal_feed_state','open')});
 await page.goto(base,{waitUntil:'domcontentloaded'});
 await page.waitForFunction(()=>document.querySelector('#feed-status').textContent.includes('16/16'));
 await page.waitForFunction(()=>document.querySelector('#news-status').textContent.includes('live articles'));
 const feed=await (await context.request.get(base+'/feed.json')).json();
 const zh=await (await context.request.get(base+'/api/zerohedge')).json();
 assert.equal(feed.diagnostics.accountsSucceeded,16);assert.equal(Object.keys(feed.diagnostics.sources).length,16);assert.equal(feed.posts.length,12);
 assert.equal(new Set(feed.posts.map(p=>p.handle)).size,12);
 const order=feed.posts.map(p=>[p.likes+p.retweets,Date.parse(p.createdAt)]);
 for(let i=0;i<order.length;i++){assert.equal(feed.posts[i].engagementScore,order[i][0]);assert(Date.now()-order[i][1]<=86400000);if(i)assert(order[i-1][0]>order[i][0]||(order[i-1][0]===order[i][0]&&order[i-1][1]>=order[i][1]))}
 assert(zh.articles.every(a=>a.excerpt.trim()&&!/&(?:amp;)*nbsp;/.test(a.excerpt)));
 const snapshot=async()=>page.evaluate(()=>({
 status:document.querySelector('#feed-status').textContent,
 zh:[...document.querySelectorAll('#zerohedge-feed article')].map(el=>({title:el.querySelector('.feed-card-title').textContent,intro:el.querySelector('.feed-card-excerpt')?.textContent,color:getComputedStyle(el.querySelector('.feed-card-excerpt')).color,height:el.getBoundingClientRect().height,footer:el.querySelector('.feed-card-source').getBoundingClientRect().bottom,href:el.querySelector('.feed-card-source').href})),
 x:[...document.querySelectorAll('#signal-feed article')].map(el=>({handle:el.querySelector('.feed-handle').textContent,time:el.querySelector('time').dateTime,url:el.querySelector('.feed-link').href})),overflow:document.documentElement.scrollWidth>innerWidth}));
 let first=await snapshot();assert.equal(first.zh.length,3);assert.equal(first.x.length,3);assert(!first.overflow);
 assert.deepEqual(first.x.map(p=>p.url),feed.posts.slice(0,3).map(p=>p.url));
 for(const item of first.zh){assert(item.intro.length<=140&&item.intro.length>15);assert(item.title.length<=110);assert(Math.abs(item.height-first.zh[0].height)<1);assert(Math.abs(item.footer-first.zh[0].footer)<1);assert.equal(item.color,'rgb(168, 164, 186)')}
 for(const id of ['zerohedge-card','signal-feed-card']){await page.locator('#'+id).scrollIntoViewIfNeeded();await page.waitForTimeout(400);await page.locator('#'+id).screenshot({path:`${out}/${id}-${width}.png`})}
 if(width<500){for(let n=0;n<3;n++){await page.locator('#zerohedge-feed article').nth(n).evaluate(el=>el.scrollIntoView({block:'center',inline:'center'}));await page.waitForTimeout(200);await page.locator('#zerohedge-card').screenshot({path:`${out}/zh-${width}-story${n+1}.png`})}}
 await page.evaluate(()=>refreshSignals(true));const second=await snapshot();assert.deepEqual(second.x.map(p=>p.url),feed.posts.slice(3,6).map(p=>p.url));
 // An actual failed retrieval must clear prior cards, not keep masquerading as current.
 await page.route('**/feed.json?*',route=>route.fulfill({json:{...feed,ok:false,error:'X API HTTP 401 Unauthorized',status:'failed'}}));
 await page.evaluate(()=>refreshSignals(true));assert.equal(await page.locator('#signal-feed article').count(),0);assert.match(await page.locator('#feed-status').textContent(),/401 Unauthorized/);
 results.push({width,first,second,failureUI:await page.locator('#feed-status').textContent()});
 if(width===1440){fs.writeFileSync(out+'/source-audit.json',JSON.stringify({feed,zerohedge:zh},null,2))}
 await context.close();
 }
 fs.writeFileSync(out+'/results.json',JSON.stringify(results,null,2));console.log('Live feed top-three, ranking, intros, equal geometry, dates, rotation, explicit failure: PASS at 1440/390/360');
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exit(1)});
