'use strict';
const crypto=require('node:crypto');
const {verifySessionCookie}=require('../lib/quote-session');
const {validatePostInput}=require('../lib/quote-validation');
const {createXClient,credentialsFromEnv,configured,XError}=require('../lib/quote-x-client');
const {json,readJson,sameOrigin}=require('../lib/quote-http');
const inFlight=new Map(),completed=new Map(),MAX_TRACKED=500,MAX_IN_FLIGHT=100,TTL_MS=10*60*1000;
function prune(now){for(const[k,v]of completed)if(v.expires<=now)completed.delete(k);if(completed.size>MAX_TRACKED){for(const k of completed.keys()){completed.delete(k);if(completed.size<=MAX_TRACKED)break;}}}
function publicError(error){if(error&&error.statusCode)return{status:error.statusCode,message:error.message,code:'invalid_request'};if(error instanceof XError){if(error.code==='not_configured')return{status:503,message:'X posting is not configured.',code:error.code};if(error.code==='wrong_account')return{status:409,message:'Posting account verification failed.',code:error.code};return{status:502,message:error.code==='ambiguous'?error.message:'X result could not be verified. Check X before retrying.',code:error.code};}return{status:500,message:'Posting result is unknown. Check X before retrying.',code:'unknown_result'};}
async function handler(req,res){
  const credentials=credentialsFromEnv();
  if(req.method==='GET')return json(res,200,{configured:configured(credentials)&&Boolean(process.env.NOS_AUTH_SECRET&&process.env.NOS_ACCESS_PIN),account:'Novairecito',authenticated:verifySessionCookie(req.headers.cookie,process.env.NOS_AUTH_SECRET||'')});
  if(req.method!=='POST')return json(res,405,{error:'Method not allowed.'},{Allow:'GET, POST'});
  if(!sameOrigin(req))return json(res,403,{error:'Same-origin request required.'});
  if(!verifySessionCookie(req.headers.cookie,process.env.NOS_AUTH_SECRET||''))return json(res,401,{error:'Quote session is missing or expired.'});
  let input;try{input=validatePostInput(await readJson(req,7*1024*1024));}catch(error){const out=publicError(error);return json(res,out.status,{error:out.message,code:out.code});}
  const key=crypto.createHash('sha256').update(input.requestId).digest('hex'),now=Date.now();prune(now);
  const cached=completed.get(key);if(cached)return json(res,200,cached.body);
  if(inFlight.has(key))return json(res,409,{error:'This request is already being processed.',code:'in_flight'},{'Retry-After':'5'});
  if(inFlight.size>=MAX_IN_FLIGHT)return json(res,503,{error:'Posting service is busy. No request was sent to X.',code:'busy'},{'Retry-After':'10'});
  const work=(async()=>{
    const result=await createXClient({credentials}).publish(input);
    return{ok:true,url:result.url,id:result.id};
  })();inFlight.set(key,work);
  try{const body=await work;completed.set(key,{body,expires:Date.now()+TTL_MS});return json(res,200,body);}catch(error){const out=publicError(error);return json(res,out.status,{error:out.message,code:out.code});}finally{inFlight.delete(key);}
}
module.exports=handler;
module.exports.config={maxDuration:60};
