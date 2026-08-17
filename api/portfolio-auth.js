const crypto=require('crypto');
const attempts=new Map();
function json(res,status,body,headers={}){res.statusCode=status;res.setHeader('Content-Type','application/json');for(const [k,v] of Object.entries(headers))res.setHeader(k,v);res.end(JSON.stringify(body))}
function safeEqual(a,b){const x=Buffer.from(String(a)),y=Buffer.from(String(b));return x.length===y.length&&crypto.timingSafeEqual(x,y)}
module.exports=async function handler(req,res){
 if(req.method!=='POST')return json(res,405,{error:'Method not allowed'},{Allow:'POST'});
 const ip=String(req.headers['x-forwarded-for']||req.socket?.remoteAddress||'unknown').split(',')[0].trim();
 const now=Date.now(),record=attempts.get(ip)||{count:0,until:0};
 if(record.until>now)return json(res,429,{error:'Too many attempts. Try again in 15 minutes.'},{'Retry-After':String(Math.ceil((record.until-now)/1000))});
 let body='';for await(const chunk of req)body+=chunk;
 let data={};try{data=JSON.parse(body||'{}')}catch{return json(res,400,{error:'Invalid request'})}
 const expected=process.env.NOS_ACCESS_PIN||'',provided=String(data.pin||'');
 if(!/^\d{5}$/.test(provided)||!expected||!safeEqual(provided,expected)){
  record.count++;if(record.count>=5){record.until=now+15*60*1000;record.count=0}attempts.set(ip,record);
  return json(res,401,{error:record.until?'Too many attempts. Locked for 15 minutes.':'Incorrect PIN.'});
 }
 attempts.delete(ip);
 const maxAge=30*60,expires=Math.floor(Date.now()/1000)+maxAge;
 const secret=process.env.NOS_AUTH_SECRET;if(!secret)return json(res,500,{error:'Portfolio lock is not configured.'});
 const payload=String(expires),signature=crypto.createHmac('sha256',secret).update(payload).digest('base64url');
 const cookie=`novaire_portfolio_session=${payload}.${signature}; Path=/portfolio; Max-Age=${maxAge}; HttpOnly; Secure; SameSite=Strict`;
 return json(res,200,{ok:true},{'Set-Cookie':cookie,'Cache-Control':'no-store'});
};
