export const config={matcher:['/portfolio','/portfolio/','/portfolio/:path*']};
function cookieValue(header,name){for(const part of String(header||'').split(';')){const [key,...rest]=part.trim().split('=');if(key===name)return rest.join('=')}return ''}
function bytes(value){return new TextEncoder().encode(value)}
function decodeBase64url(value){const base=value.replace(/-/g,'+').replace(/_/g,'/').padEnd(Math.ceil(value.length/4)*4,'=');const raw=atob(base);return Uint8Array.from(raw,c=>c.charCodeAt(0))}
async function validSession(request){
 const token=cookieValue(request.headers.get('cookie'),'novaire_portfolio_session'),dot=token.indexOf('.');
 if(dot<1||!process.env.NOS_AUTH_SECRET)return false;
 const expiry=token.slice(0,dot),signature=token.slice(dot+1);
 if(!/^\d+$/.test(expiry)||Number(expiry)<Math.floor(Date.now()/1000))return false;
 try{const key=await crypto.subtle.importKey('raw',bytes(process.env.NOS_AUTH_SECRET),{name:'HMAC',hash:'SHA-256'},false,['verify']);return crypto.subtle.verify('HMAC',key,decodeBase64url(signature),bytes(expiry))}catch{return false}
}
export default async function middleware(request){
 if(await validSession(request))return;
 return Response.redirect(new URL('/portfolio-lock.html',request.url),302);
}
