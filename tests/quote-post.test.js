'use strict';

// All X calls in this suite use injected fetch mocks. This file never contacts X
// and never uploads media or creates a real post.
const test = require('node:test');
const assert = require('node:assert/strict');
const zlib = require('node:zlib');
const crypto = require('node:crypto');

const { createSessionCookie, verifySessionCookie } = require('../lib/quote-session');
const { validatePostInput, parsePngDataUrl } = require('../lib/quote-validation');
const { createXClient } = require('../lib/quote-x-client');
const { sameOrigin } = require('../lib/quote-http');
const quotePostHandler = require('../api/quote-post');
const quoteAuthHandler = require('../api/quote-auth');
function mockRes(){return{statusCode:0,headers:{},body:null,setHeader(k,v){this.headers[k]=v;},end(v){this.body=JSON.parse(v);}};}

function chunk(type, data) {
  const name = Buffer.from(type);
  const crc = crc32(Buffer.concat([name, data]));
  const out = Buffer.alloc(12 + data.length);
  out.writeUInt32BE(data.length, 0); name.copy(out, 4); data.copy(out, 8);
  out.writeUInt32BE(crc >>> 0, 8 + data.length);
  return out;
}
function crc32(buffer) {
  let crc = 0xffffffff;
  for (const byte of buffer) {
    crc ^= byte;
    for (let bit = 0; bit < 8; bit++) crc = (crc >>> 1) ^ ((crc & 1) ? 0xedb88320 : 0);
  }
  return (crc ^ 0xffffffff) >>> 0;
}
function pngDataUrl() {
  const ihdr = Buffer.alloc(13); ihdr.writeUInt32BE(1, 0); ihdr.writeUInt32BE(1, 4); ihdr[8] = 8; ihdr[9] = 6;
  const raw = Buffer.from([0, 255, 0, 0, 255]);
  const png = Buffer.concat([
    Buffer.from('89504e470d0a1a0a', 'hex'), chunk('IHDR', ihdr),
    chunk('IDAT', zlib.deflateSync(raw)), chunk('IEND', Buffer.alloc(0))
  ]);
  return `data:image/png;base64,${png.toString('base64')}`;
}
const creds = { consumerKey:'ck', consumerSecret:'cs', accessToken:'at', accessTokenSecret:'as' };
function response(status, body) { return { ok: status >= 200 && status < 300, status, json: async () => body }; }

test('image-only validation still requires PNG and confirmation', () => {
  const data={text:'',imageDataUrl:pngDataUrl(),confirmation:true,requestId:crypto.randomUUID()};
  assert.equal(validatePostInput(data).text,'');
  assert.throws(()=>validatePostInput({...data,imageDataUrl:''}));
  assert.throws(()=>validatePostInput({...data,confirmation:false}));
});

test('image-only upload omits text and verifies the exact attached media',async()=>{
 const calls=[];
 const client=createXClient({credentials:creds,fetchImpl:async(url,init)=>{
  calls.push([url,init]);
  if(url.endsWith('/2/users/me'))return response(200,{data:{id:'42',username:'Novairecito'}});
  if(url.endsWith('/2/media/upload'))return response(200,{data:{id:'77'}});
  if(url.endsWith('/2/tweets')){assert.deepEqual(JSON.parse(init.body),{media:{media_ids:['77']}});return response(201,{data:{id:'88'}});}
  if(url.includes('/2/tweets/88?'))return response(200,{data:{id:'88',author_id:'42',text:'https://t.co/card',attachments:{media_keys:['3_77']},entities:{urls:[{url:'https://t.co/card',expanded_url:'https://x.com/Novairecito/status/88/photo/1'}]}}});
  throw Error('Unexpected request '+url);
 }});
 assert.equal((await client.publish({text:'',png:Buffer.from('mock-png')})).id,'88');
 assert.equal(calls.length,4);
});

test('image-only uncertain create cannot reconcile to another image-only post',async()=>{
 let creates=0;
 const client=createXClient({credentials:creds,fetchImpl:async(url,init)=>{
  if(url.endsWith('/2/users/me'))return response(200,{data:{id:'42',username:'Novairecito'}});
  if(url.endsWith('/2/media/upload'))return response(200,{data:{id:'77'}});
  if(url.endsWith('/2/tweets')){creates++;throw Error('mock network timeout');}
  if(url.includes('/2/users/42/tweets?'))return response(200,{data:[{id:'99',author_id:'42',text:'',attachments:{media_keys:['3_66']},created_at:new Date().toISOString()}]});
  throw Error('Unexpected request '+url);
 }});
 await assert.rejects(()=>client.publish({text:'',png:Buffer.from('mock-png')}),e=>e.code==='ambiguous');
 assert.equal(creates,1);
});

test('quote session is scoped, signed, and expires', () => {
  const cookie = createSessionCookie('secret', 1000);
  assert.match(cookie, /^quote_session=/);
  assert.match(cookie, /Path=\/api; Max-Age=1800; HttpOnly; Secure; SameSite=Strict/);
  const pair = cookie.split(';')[0];
  assert.equal(verifySessionCookie(pair, 'secret', 1001), true);
  assert.equal(verifySessionCookie(pair, 'wrong', 1001), false);
  assert.equal(verifySessionCookie(pair, 'secret', 2801), false);
});

test('validation accepts the frontend quote/newline/author fixture and rejects URLs/source markers', () => {
  const fixture='“Civilization compounds through trust.”\n— Novaire';
  const good = validatePostInput({ text:fixture, imageDataUrl:pngDataUrl(), confirmation:true, requestId:crypto.randomUUID() });
  assert.equal(good.text, fixture);
  assert.equal(good.png[0], 0x89);
  for (const text of ['See https://example.com', 'visit www.example.com', 'Novaire Signal', 'novairesignal']) {
    assert.throws(() => validatePostInput({ text, imageDataUrl:pngDataUrl(), confirmation:true, requestId:crypto.randomUUID() }), /not allowed/i);
  }
});

test('PNG parser rejects a signature-only fake and corrupt CRC', () => {
  assert.throws(() => parsePngDataUrl(`data:image/png;base64,${Buffer.from('89504e470d0a1a0a','hex').toString('base64')}`), /PNG/);
  const corrupt = pngDataUrl().replace(/.$/, 'A');
  assert.throws(() => parsePngDataUrl(corrupt), /PNG|base64/);
});

test('weighted text limit is conservative for CJK and astral characters', () => {
  const base = { imageDataUrl:pngDataUrl(), confirmation:true, requestId:crypto.randomUUID() };
  assert.doesNotThrow(() => validatePostInput({ ...base, text:'a'.repeat(280) }));
  assert.throws(() => validatePostInput({ ...base, text:'界'.repeat(141) }), /280/);
  assert.throws(() => validatePostInput({ ...base, text:'😀'.repeat(141) }), /280/);
});

test('X client verifies account, checks duplicate, uploads, creates, and reads back exact post', async () => {
  const calls = [];
  const fetchMock = async (url, options) => {
    calls.push({ url:String(url), options });
    if (String(url).endsWith('/2/users/me')) return response(200,{data:{id:'42',username:'Novairecito'}});
    if (String(url).includes('/2/users/42/tweets')) return response(200,{data:[]});
    if (String(url).endsWith('/2/media/upload')) return response(200,{data:{id:'99'}});
    if (String(url).endsWith('/2/tweets') && options.method==='POST') return response(201,{data:{id:'123',text:'A post'}});
    if (String(url).includes('/2/tweets/123')) return response(200,{data:{id:'123',text:'A post https://t.co/photo',author_id:'42',attachments:{media_keys:['3_99']},entities:{urls:[{url:'https://t.co/photo',expanded_url:'https://x.com/Novairecito/status/123/photo/1'}]}}});
    throw new Error('unexpected mock URL');
  };
  const client = createXClient({ fetchImpl:fetchMock, credentials:creds, timeoutMs:1000 });
  const result = await client.publish({text:'A post',png:parsePngDataUrl(pngDataUrl())});
  assert.deepEqual(result,{id:'123',url:'https://x.com/Novairecito/status/123',replayed:false});
  assert.equal(calls.length,5);
  assert.ok(calls.every(c => /^OAuth /.test(c.options.headers.Authorization)));
  const uploadBody = JSON.parse(calls[2].options.body);
  assert.equal(uploadBody.media_category,'tweet_image');
  assert.equal(typeof uploadBody.media,'string');
});

test('X client aborts before upload when username is not exact', async () => {
  let calls=0;
  const client=createXClient({credentials:creds,fetchImpl:async()=>{calls++;return response(200,{data:{id:'42',username:'impostor'}})}});
  await assert.rejects(()=>client.publish({text:'A post',png:Buffer.from('x')}),/account verification/i);
  assert.equal(calls,1);
});

test('X client treats recent exact post as a safe replay and does not upload', async () => {
  let calls=0;
  const client=createXClient({credentials:creds,fetchImpl:async(url)=>{
    calls++;
    if(String(url).endsWith('/2/users/me'))return response(200,{data:{id:'42',username:'Novairecito'}});
    if(String(url).includes('/2/users/42/tweets'))return response(200,{data:[{id:'777',text:'Same',created_at:new Date().toISOString(),author_id:'42'}]});
    if(String(url).includes('/2/tweets/777'))return response(200,{data:{id:'777',text:'Same',author_id:'42'}});
    throw new Error('upload should not occur');
  }});
  assert.deepEqual(await client.publish({text:'Same',png:Buffer.from('x')}),{id:'777',url:'https://x.com/Novairecito/status/777',replayed:true});
  assert.equal(calls,3);
});

test('auth handler enforces origin and rejects null/wrong PIN without a cookie', async () => {
  const oldPin=process.env.NOS_ACCESS_PIN,oldSecret=process.env.NOS_AUTH_SECRET;
  process.env.NOS_ACCESS_PIN='12345';process.env.NOS_AUTH_SECRET='secret';
  const base={method:'POST',headers:{host:'signal.example',origin:'https://signal.example'},socket:{remoteAddress:'test-auth'}};
  let res=mockRes();await quoteAuthHandler({...base,headers:{...base.headers,origin:'https://evil.example'},body:{pin:'12345'}},res);assert.equal(res.statusCode,403);
  res=mockRes();await quoteAuthHandler({...base,body:null},res);assert.equal(res.statusCode,400);
  res=mockRes();await quoteAuthHandler({...base,body:{pin:'99999'}},res);assert.equal(res.statusCode,401);assert.equal(res.headers['Set-Cookie'],undefined);
  if(oldPin===undefined)delete process.env.NOS_ACCESS_PIN;else process.env.NOS_ACCESS_PIN=oldPin;
  if(oldSecret===undefined)delete process.env.NOS_AUTH_SECRET;else process.env.NOS_AUTH_SECRET=oldSecret;
});

test('post handler rejects a missing session before parsing or calling X', async () => {
  const old=process.env.NOS_AUTH_SECRET;process.env.NOS_AUTH_SECRET='secret';
  const res=mockRes();await quotePostHandler({method:'POST',headers:{host:'signal.example',origin:'https://signal.example'},body:{}},res);
  assert.equal(res.statusCode,401);assert.match(res.body.error,/session/i);
  if(old===undefined)delete process.env.NOS_AUTH_SECRET;else process.env.NOS_AUTH_SECRET=old;
});

test('GET status reports cookie authentication without contacting X', async () => {
  const previous={...process.env};
  Object.assign(process.env,{NOS_AUTH_SECRET:'secret',NOS_ACCESS_PIN:'12345',X_NOVAIRECITO_CONSUMER_KEY:'a',X_NOVAIRECITO_CONSUMER_SECRET:'b',X_NOVAIRECITO_ACCESS_TOKEN:'c',X_NOVAIRECITO_ACCESS_TOKEN_SECRET:'d'});
  const cookie=createSessionCookie('secret',Math.floor(Date.now()/1000)).split(';')[0];
  let output;
  const res={headers:{},setHeader(k,v){this.headers[k]=v;},end(v){output=JSON.parse(v);}};
  await quotePostHandler({method:'GET',headers:{cookie}},res);
  assert.deepEqual(output,{configured:true,account:'Novairecito',authenticated:true});
  for(const key of Object.keys(process.env))if(!(key in previous))delete process.env[key];Object.assign(process.env,previous);
});

test('same-origin check requires exact forwarded scheme and host', () => {
  assert.equal(sameOrigin({headers:{origin:'https://signal.example','x-forwarded-host':'signal.example','x-forwarded-proto':'https'}}),true);
  assert.equal(sameOrigin({headers:{origin:'https://evil.example','x-forwarded-host':'signal.example','x-forwarded-proto':'https'}}),false);
  assert.equal(sameOrigin({headers:{origin:'http://signal.example','x-forwarded-host':'signal.example','x-forwarded-proto':'https'}}),false);
  assert.equal(sameOrigin({headers:{host:'signal.example'}}),false);
});

test('ambiguous create failure is reconciled once without retrying POST', async () => {
  let timelineChecks=0, postAttempts=0;
  const client=createXClient({credentials:creds,fetchImpl:async(url,options)=>{
    if(String(url).endsWith('/2/users/me'))return response(200,{data:{id:'42',username:'Novairecito'}});
    if(String(url).includes('/2/users/42/tweets')) {
      timelineChecks++;
      return timelineChecks===1 ? response(200,{data:[]}) : response(200,{data:[{id:'888',text:'Maybe',created_at:new Date().toISOString()}]});
    }
    if(String(url).endsWith('/2/media/upload'))return response(200,{data:{id:'99'}});
    if(String(url).endsWith('/2/tweets')&&options.method==='POST'){postAttempts++;throw new Error('timeout');}
    if(String(url).includes('/2/tweets/888'))return response(200,{data:{id:'888',text:'Maybe',author_id:'42'}});
    throw new Error('unexpected');
  }});
  const out=await client.publish({text:'Maybe',png:Buffer.from('x')});
  assert.equal(out.id,'888'); assert.equal(out.replayed,true); assert.equal(postAttempts,1);
});
