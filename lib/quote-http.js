'use strict';
function json(res,status,body,headers={}){res.statusCode=status;res.setHeader('Content-Type','application/json; charset=utf-8');res.setHeader('Cache-Control','no-store');for(const[k,v]of Object.entries(headers))res.setHeader(k,v);res.end(JSON.stringify(body));}
async function readJson(req,maxBytes){
  if(req.body!==undefined){const size=Buffer.byteLength(typeof req.body==='string'?req.body:JSON.stringify(req.body));if(size>maxBytes){const e=new Error('Request too large.');e.statusCode=413;throw e;}if(typeof req.body==='string'){try{return JSON.parse(req.body||'{}');}catch{const e=new Error('Invalid request.');e.statusCode=400;throw e;}}return req.body;}
  let size=0,body='';for await(const chunk of req){size+=Buffer.byteLength(chunk);if(size>maxBytes){const e=new Error('Request too large.');e.statusCode=413;throw e;}body+=chunk;}
  try{return JSON.parse(body||'{}');}catch{const e=new Error('Invalid request.');e.statusCode=400;throw e;}
}
function sameOrigin(req){
  const origin=req.headers&&req.headers.origin;if(typeof origin!=='string'||!origin)return false;
  const host=String(req.headers['x-forwarded-host']||req.headers.host||'').trim().toLowerCase();
  const proto=String(req.headers['x-forwarded-proto']||'https').split(',')[0].trim().toLowerCase();
  try{const url=new URL(origin);return !url.username&&!url.password&&url.pathname==='/'&&!url.search&&!url.hash&&url.protocol===`${proto}:`&&url.host.toLowerCase()===host;}catch{return false;}
}
module.exports={json,readJson,sameOrigin};
