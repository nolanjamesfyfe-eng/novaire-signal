#!/usr/bin/env node
'use strict';
const fs=require('node:fs');
const assert=require('node:assert/strict');
(async()=>{
 const source=fs.readFileSync(require('node:path').join(__dirname,'../api/zerohedge.js'),'utf8');
 const {default:handler}=await import('data:text/javascript;base64,'+Buffer.from(source).toString('base64'));
 const original=global.fetch;
 try {
  for(const host of ['assets.zerohedge.com','cms.zerohedge.com','evil.example','cms.zerohedge.com.evil.example']){
   const image=`https://${host}/sites/default/files/inline-images/article.jpg`;
   global.fetch=async()=>new Response(`<rss><channel><item><title>Publisher supplied article title</title><link>https://www.zerohedge.com/markets/test</link><description><![CDATA[<p>The publisher supplied this genuine article introduction.</p><img src="${image}" alt="Article image">]]></description></item></channel></rss>`);
   const r=await handler({method:'GET'}),data=await r.json();
   assert.equal(r.status,200);assert.equal(data.articles[0].image,host==='assets.zerohedge.com'||host==='cms.zerohedge.com'?image:'');
  }
 } finally {global.fetch=original;}
 console.log('PASS: API retains genuine asset/CMS images and rejects foreign/lookalike hosts');
})().catch(e=>{console.error(e);process.exit(1);});
