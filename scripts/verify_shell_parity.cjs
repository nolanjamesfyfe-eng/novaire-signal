#!/usr/bin/env node
const {chromium}=require('/root/clawd/novaire-operations-system/node_modules/playwright');
const fs=require('fs'),assert=require('assert/strict');
const base=process.env.SIGNAL_BASE_URL||'https://novairesignal.com/';
const local=base.includes('127.0.0.1');
const out=process.env.EVIDENCE_DIR||process.env.TMPDIR+'/shell-parity';
const baseline=process.env.BASELINE?JSON.parse(fs.readFileSync(process.env.BASELINE)):null;
const routes=['','flaneur','health','portfolio/','portfolio/daily/','portfolio/evolutionfund/','portfolio/evolutionfund/philosophy.html','portfolio/finances/','portfolio-lock.html'];
const props=['fontFamily','fontSize','fontWeight','fontStyle','letterSpacing','lineHeight','textTransform','color'];
(async()=>{
 fs.mkdirSync(out,{recursive:true});
 const browser=await chromium.launch({executablePath:'/opt/google/chrome/chrome',args:['--no-sandbox']});
 const context=await browser.newContext({reducedMotion:'reduce'});
 if(process.env.SIGNAL_AUTH==='1'){
  const secrets=fs.readFileSync('/root/clawd/.secrets','utf8');
  const pin=secrets.match(/^NOS_ACCESS_PIN=(.*)$/m)?.[1].trim().replace(/^['"]|['"]$/g,'');
  assert(pin,'Configured auth credential missing');
  const res=await context.request.post(base+'api/portfolio-auth',{data:{pin}});
  assert(res.ok(),`Portfolio auth failed ${res.status()}`);
 }
 const results=[];let failure;
 try{
 for(const width of [320,360,390,430,1440]){
  let canonical;
  for(const route of routes){
   const page=await context.newPage();await page.setViewportSize({width,height:900});
   await page.goto(base+(local&&route==='flaneur'?'map/':route),{waitUntil:'domcontentloaded'});
   await page.evaluate(()=>document.fonts.ready);await page.waitForTimeout(300);
   const data=await page.evaluate(props=>{
    const sample=e=>{const s=getComputedStyle(e),r=e.getBoundingClientRect();return {text:e.textContent.trim(),css:Object.fromEntries(props.map(k=>[k,s[k]])),box:{x:r.x,y:r.y,width:r.width,height:r.height}}};
    return {zoom:getComputedStyle(document.body).zoom,overflow:document.documentElement.scrollWidth>innerWidth,rows:[...document.querySelectorAll('.signal-brand-row')].map(e=>({row:sample(e),children:[...e.children].map(sample),paint:[...e.querySelectorAll('svg,.signal-wordmark>span')].map(sample),links:[...e.querySelectorAll('a')].map(a=>a.getAttribute('href'))})),taglines:[...document.querySelectorAll('.signal-tagline,.footer-tagline')].map(sample),headings:[...document.querySelectorAll('h1,h2,.stat-value,.legend')].map(sample),globe:document.querySelector('#globe-canvas')?.getAttribute('data-diameter')};
   },props);
   results.push({width,route,...data});
   const name=route.replaceAll('/','_')||'home';
   await page.screenshot({path:`${out}/${name}-${width}.png`,fullPage:route==='flaneur'});
   if(data.rows.length){await page.evaluate(()=>{document.documentElement.style.scrollBehavior='auto';document.querySelectorAll('.signal-brand-row')[1].scrollIntoView({behavior:'instant',block:'center'})});await page.screenshot({path:`${out}/${name}-footer-${width}.png`});}
   if(!route)canonical=data;
   if(!process.env.RECORD_ONLY){
    assert.equal(data.rows.length,2,`two genuine brand rows: ${route} ${width}`);
    assert(!data.overflow,`document overflow ${route} ${width}`);
    for(const row of data.rows){
     for(const [i,child] of row.children.entries()){
      const ref=canonical.rows[0].children[i];
      assert.deepEqual(child.css,ref.css,`computed brand ${route} ${width} child ${i}`);
      for(const key of ['width','height'])assert(Math.abs(child.box[key]-ref.box[key])<.16,`rendered ${key} ${route} ${width} child ${i}: ${child.box[key]} vs ${ref.box[key]}`);
      const gap=child.box.x-row.row.box.x,refgap=ref.box.x-canonical.rows[0].row.box.x;
      assert(Math.abs(gap-refgap)<.16,`icon/wordmark spacing ${route} ${width}`);
      assert(child.box.x>=5&&child.box.x+child.box.width<=width-5,`clipped brand ${route} ${width}`);
     }
     for(const [i,paint] of row.paint.entries()){
      const ref=canonical.rows[0].paint[i];assert.deepEqual(paint.css,ref.css,`actual SVG/italic style ${route} ${width}`);
      for(const key of ['width','height'])assert(Math.abs(paint.box[key]-ref.box[key])<.16,`painted dimensions ${route} ${width}`);
     }
     assert.deepEqual(row.links,canonical.rows[0].links,`brand links ${route}`);
    }
    if(!route){
     const before=baseline?.find(x=>x.width===width&&!x.route);
     if(before){assert.equal(data.zoom,before.zoom,'immutable homepage zoom');
     for(let i=0;i<2;i++){
      assert.equal(data.rows[i].row.box.width,before.rows[i].row.box.width,'immutable homepage width');
      for(const key of ['fontFamily','fontSize','fontWeight','fontStyle','letterSpacing','lineHeight'])assert.equal(data.rows[i].children[1].css[key],before.rows[i].children[1].css[key],'immutable homepage typography');
     }}
     assert.deepEqual(data.taglines[0].css,data.taglines[1].css,'pending footer tagline parity');
    }
    if(route==='flaneur'&&width===390)assert.equal(data.globe,'374','unchanged uncropped globe');
   }
   await page.close();
  }
 }
 }catch(e){failure=e}finally{await browser.close();fs.writeFileSync(out+'/results.json',JSON.stringify(results,null,2))}
 if(failure)throw failure;
 console.log(process.env.RECORD_ONLY?`RECORDED ${results.length} route/viewports (assertions disabled)`:`PASS ${results.length} route/viewports: computed type, SVG geometry, icon spacing, links, no clipping/overflow, immutable home and footer tagline.`);
})().catch(e=>{console.error(e);process.exit(1)});
