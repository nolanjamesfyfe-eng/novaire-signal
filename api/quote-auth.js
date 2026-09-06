'use strict';
const {createSessionCookie,safeEqual}=require('../lib/quote-session');
const {json,readJson,sameOrigin}=require('../lib/quote-http');

// Serverless caveat: this bounded limiter is per warm instance, not globally shared.
// It fails closed when its 10,000-key capacity is exhausted, preventing unbounded
// memory growth. Platform/WAF rate limiting should be added for global protection.
const attempts=new Map(),MAX_KEYS=10000,MAX_ATTEMPTS=5,LOCK_MS=15*60*1000;
function clientKey(req){return String(req.headers['x-forwarded-for']||req.socket&&req.socket.remoteAddress||'unknown').split(',')[0].trim().slice(0,128)||'unknown';}
module.exports=async function handler(req,res){
  if(req.method!=='POST')return json(res,405,{error:'Method not allowed.'},{Allow:'POST'});
  if(!sameOrigin(req))return json(res,403,{error:'Same-origin request required.'});
  const pin=process.env.NOS_ACCESS_PIN||'',secret=process.env.NOS_AUTH_SECRET||'';
  if(!/^\d{5}$/.test(pin)||!secret)return json(res,503,{error:'Quote posting authentication is not configured.'});
  const key=clientKey(req),now=Date.now();let record=attempts.get(key);
  if(!record&&attempts.size>=MAX_KEYS)return json(res,503,{error:'Authentication is temporarily unavailable.'},{'Retry-After':'900'});
  record=record||{failures:0,lockedUntil:0};
  if(record.lockedUntil>now)return json(res,429,{error:'Too many attempts. Try again later.'},{'Retry-After':String(Math.ceil((record.lockedUntil-now)/1000))});
  if(record.lockedUntil){record.lockedUntil=0;record.failures=0;}
  let data;try{data=await readJson(req,1024);}catch(error){return json(res,error.statusCode||400,{error:error.message});}
  if(!data||typeof data!=='object'||Array.isArray(data))return json(res,400,{error:'Invalid request.'});
  const provided=typeof data.pin==='string'?data.pin:'';
  if(!/^\d{5}$/.test(provided)||!safeEqual(provided,pin)){
    record.failures++;if(record.failures>=MAX_ATTEMPTS){record.failures=0;record.lockedUntil=now+LOCK_MS;}attempts.set(key,record);
    return json(res,record.lockedUntil?429:401,{error:record.lockedUntil?'Too many attempts. Try again later.':'Incorrect PIN.'},record.lockedUntil?{'Retry-After':'900'}:{});
  }
  attempts.delete(key);
  return json(res,200,{ok:true},{'Set-Cookie':createSessionCookie(secret),'X-Content-Type-Options':'nosniff'});
};
