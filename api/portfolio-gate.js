const fs=require('fs');
const path=require('path');
const crypto=require('crypto');
function parseCookies(header=''){return Object.fromEntries(header.split(';').map(x=>x.trim().split(/=(.*)/s)).filter(x=>x[0]))}
function validSession(req){
 const value=parseCookies(req.headers.cookie||'').novaire_portfolio_session;if(!value)return false;
 const [expiry,sig]=value.split('.');if(!expiry||!sig||Number(expiry)<Math.floor(Date.now()/1000))return false;
 const secret=process.env.NOS_AUTH_SECRET;if(!secret)return false;
 const expected=crypto.createHmac('sha256',secret).update(expiry).digest('base64url'),a=Buffer.from(sig),b=Buffer.from(expected);
 return a.length===b.length&&crypto.timingSafeEqual(a,b);
}
function portfolioFile(req){
 const raw=String(req.query?.path||'').replace(/^\/+|\/+$/g,'');
 if(!raw)return 'index.html';
 if(raw==='evolutionfund')return path.join('evolutionfund','index.html');
 if(raw==='finances')return path.join('finances','index.html');
 return null;
}
module.exports=function handler(req,res){
 res.setHeader('Cache-Control','private, no-store, max-age=0');
 if(!validSession(req)){res.statusCode=302;res.setHeader('Location','/portfolio-lock.html');return res.end()}
 const rel=portfolioFile(req);if(!rel){res.statusCode=404;return res.end('Not found')}
 const html=fs.readFileSync(path.join(process.cwd(),'portfolio',rel),'utf8');
 res.statusCode=200;res.setHeader('Content-Type','text/html; charset=utf-8');res.end(html);
};
