'use strict';
const { requestOriginAllowed, verifySession } = require('../lib/health-session');
const store = require('../lib/health-checkin-store');

function respond(res,status,body,extra={}){res.statusCode=status;res.setHeader('Content-Type','application/json; charset=utf-8');res.setHeader('Cache-Control','private, no-store, max-age=0');res.setHeader('Pragma','no-cache');res.setHeader('X-Robots-Tag','noindex, nofollow, noarchive');for(const [k,v] of Object.entries(extra))res.setHeader(k,v);res.end(JSON.stringify(body));}
async function json(req,max=64*1024){let body='';for await(const chunk of req){body+=chunk;if(Buffer.byteLength(body)>max)throw Object.assign(new Error(),{status:413});}try{return JSON.parse(body||'{}')}catch{throw Object.assign(new Error(),{status:400})}}
module.exports=async function handler(req,res){
  if(!['GET','PUT','POST'].includes(req.method))return respond(res,405,{error:'Method not allowed'},{Allow:'GET, PUT, POST'});
  if(!requestOriginAllowed(req))return respond(res,403,{error:'Forbidden'});
  if(!verifySession(req.headers.cookie,process.env.NOS_AUTH_SECRET||''))return respond(res,401,{error:'Authentication required'});
  if(!store.config())return respond(res,503,{error:'Private cross-device check-in storage is not configured.'});
  try{
    const current=await store.read();
    if(req.method==='GET'){
      const headers={'ETag':`"${current.revision}"`,'Content-Disposition':'attachment; filename="novaire-health-checkins.json"'};
      return respond(res,200,{revision:current.revision,entries:current.entries,exportedAt:new Date().toISOString()},headers);
    }
    const body=await json(req);
    const expected=Number(body.revision);
    if(!Number.isInteger(expected)||expected<0)return respond(res,428,{error:'A current revision is required.'});
    if(expected!==current.revision)return respond(res,409,{error:'Check-ins changed on another device.',revision:current.revision});
    let entries=current.entries.slice(), conflicts=[];
    if(req.method==='PUT'){
      const entry=store.sanitize(body.entry);if(!entry)return respond(res,422,{error:'Invalid check-in.'});
      const index=entries.findIndex(x=>x.date===entry.date);
      if(index>=0&&body.confirmOverwrite!==true)return respond(res,409,{error:'That date already exists. Confirm before replacing it.',conflict:entries[index]});
      const saved={...entry,updatedAt:new Date().toISOString()};if(index>=0)entries[index]=saved;else entries.push(saved);
    } else {
      if(!Array.isArray(body.entries)||body.entries.length>store.MAX_RECORDS)return respond(res,422,{error:'Invalid import.'});
      for(const raw of body.entries){const entry=store.sanitize(raw);if(!entry)return respond(res,422,{error:'Invalid import entry.'});if(entries.some(x=>x.date===entry.date)){conflicts.push(entry.date);continue;}entries.push({...entry,updatedAt:new Date().toISOString()});}
    }
    entries.sort((a,b)=>a.date.localeCompare(b.date));
    const next={revision:current.revision+1,entries};
    if(!await store.compareAndSet(current.revision,next))return respond(res,409,{error:'Check-ins changed on another device. Reload and retry.'});
    return respond(res,200,{revision:next.revision,entries:next.entries,conflicts});
  }catch(error){
    if(error&&error.status===413)return respond(res,413,{error:'Request too large'});
    if(error&&error.status===400)return respond(res,400,{error:'Invalid JSON'});
    if(error&&error.code==='LIMIT')return respond(res,413,{error:'Check-in storage limit reached.'});
    return respond(res,503,{error:'Private check-in storage is temporarily unavailable.'});
  }
};
