'use strict';
const crypto = require('node:crypto');
const COOKIE_NAME = 'quote_session';
const MAX_AGE = 30 * 60;
function b64json(value){return Buffer.from(JSON.stringify(value)).toString('base64url');}
function mac(value,secret){return crypto.createHmac('sha256',secret).update(value).digest('base64url');}
function safeEqual(a,b){const x=Buffer.from(String(a)),y=Buffer.from(String(b));return x.length===y.length&&crypto.timingSafeEqual(x,y);}
function createSessionCookie(secret, nowSeconds=Math.floor(Date.now()/1000)){
  if(!secret)throw new Error('Missing session secret');
  const payload=b64json({iat:nowSeconds,exp:nowSeconds+MAX_AGE,nonce:crypto.randomBytes(16).toString('base64url')});
  return `${COOKIE_NAME}=${payload}.${mac(payload,secret)}; Path=/api; Max-Age=${MAX_AGE}; HttpOnly; Secure; SameSite=Strict`;
}
function cookieValue(header){
  for(const part of String(header||'').split(';')){const i=part.indexOf('=');if(i>0&&part.slice(0,i).trim()===COOKIE_NAME)return part.slice(i+1).trim();}
  return '';
}
function verifySessionCookie(cookieHeader,secret,nowSeconds=Math.floor(Date.now()/1000)){
  if(!secret)return false;
  const value=cookieValue(cookieHeader),dot=value.lastIndexOf('.');if(dot<1)return false;
  const payload=value.slice(0,dot),signature=value.slice(dot+1);if(!safeEqual(signature,mac(payload,secret)))return false;
  try{const data=JSON.parse(Buffer.from(payload,'base64url').toString());return Number.isInteger(data.iat)&&Number.isInteger(data.exp)&&typeof data.nonce==='string'&&data.iat<=nowSeconds+30&&data.exp>=nowSeconds&&data.exp-data.iat===MAX_AGE;}catch{return false;}
}
module.exports={COOKIE_NAME,MAX_AGE,createSessionCookie,verifySessionCookie,safeEqual};
