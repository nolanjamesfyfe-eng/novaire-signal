const assert = require('node:assert/strict');
const fs = require('node:fs');
(async()=>{
 const code=fs.readFileSync('api/zerohedge.js','utf8');
 const m=await import('data:text/javascript;base64,'+Buffer.from(code).toString('base64'));
 const sentence='Actual election results show neither bloc winning a majority.';
 for(const blank of ['&nbsp;','&amp;nbsp;','&amp;amp;nbsp;','&#160;','&#xA0;','\u00a0']){
  assert.equal(m.firstSourcedSentence(`<p>${blank}</p><p>Chart: seats</p><p>${sentence}</p>`),sentence);
  assert.equal(m.firstSourcedSentence(`<p>${blank}</p>`),'');
 }
 assert.equal(m.publicIntro(`<meta property="og:description" content="&amp;nbsp;"><article><p>&nbsp;</p><p>${sentence}</p></article>`),sentence);
 assert.equal(m.publicIntro(`<meta name="description" content="${sentence}">`),sentence);
 assert.equal(m.publicIntro('<article><p>&nbsp;</p></article>'),'');
 const realFetch=global.fetch;
 global.fetch=async url=>String(url).includes('feedburner')?new Response(`<rss><item><title>A missing metadata regression story</title><link>https://www.zerohedge.com/markets/test</link><description>&amp;nbsp;</description></item></rss>`):new Response(`<meta property="og:description" content="${sentence}">`);
 const data=await (await m.default({method:'GET'})).json();
 assert.equal(data.articles[0].excerpt,sentence);
 assert.equal(data.articles[0].excerptSource,'public_article_metadata_or_article');
 global.fetch=realFetch;
 console.log('ZeroHedge entity + public metadata fallback regression PASS');
})().catch(e=>{console.error(e);process.exit(1)});
