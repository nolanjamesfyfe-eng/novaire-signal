'use strict';
const crypto=require('node:crypto');
const API='https://api.x.com';
class XError extends Error{constructor(message,code='x_error'){super(message);this.name='XError';this.code=code;}}
function enc(v){return encodeURIComponent(String(v)).replace(/[!'()*]/g,c=>`%${c.charCodeAt(0).toString(16).toUpperCase()}`);}
function oauthHeader(method,url,credentials){
  const u=new URL(url),oauth={oauth_consumer_key:credentials.consumerKey,oauth_nonce:crypto.randomBytes(18).toString('hex'),oauth_signature_method:'HMAC-SHA1',oauth_timestamp:String(Math.floor(Date.now()/1000)),oauth_token:credentials.accessToken,oauth_version:'1.0'};
  const params=[];for(const [k,v] of u.searchParams)params.push([k,v]);for(const [k,v]of Object.entries(oauth))params.push([k,v]);
  // RFC 5849 requires bytewise sorting of percent-encoded names and values.
  params.sort((a,b)=>Buffer.compare(Buffer.from(enc(a[0])),Buffer.from(enc(b[0])))||Buffer.compare(Buffer.from(enc(a[1])),Buffer.from(enc(b[1]))));
  const base=`${method.toUpperCase()}&${enc(`${u.protocol}//${u.host}${u.pathname}`)}&${enc(params.map(([k,v])=>`${enc(k)}=${enc(v)}`).join('&'))}`;
  oauth.oauth_signature=crypto.createHmac('sha1',`${enc(credentials.consumerSecret)}&${enc(credentials.accessTokenSecret)}`).update(base).digest('base64');
  return 'OAuth '+Object.keys(oauth).sort().map(k=>`${enc(k)}="${enc(oauth[k])}"`).join(', ');
}
function configured(credentials){return Object.values(credentials).every(v=>typeof v==='string'&&v.length>0);}
function createXClient({fetchImpl=global.fetch,credentials,timeoutMs=8000}){
  if(typeof fetchImpl!=='function')throw new Error('fetch unavailable');if(!configured(credentials))throw new XError('X posting is not configured.','not_configured');
  async function request(method,path,body){
    const url=path.startsWith('http')?path:`${API}${path}`,controller=new AbortController(),timer=setTimeout(()=>controller.abort(),timeoutMs);
    const headers={Authorization:oauthHeader(method,url,credentials),Accept:'application/json'};if(body!==undefined)headers['Content-Type']='application/json';
    try{const res=await fetchImpl(url,{method,headers,body:body===undefined?undefined:JSON.stringify(body),signal:controller.signal,redirect:'error'});let data;try{data=await res.json();}catch{throw new XError('X returned an unreadable response.','bad_response');}if(!res.ok)throw new XError('X rejected the request.','rejected');return data;}finally{clearTimeout(timer);}
  }
  function verifiedText(post,id,expectedMediaId){
    if(!post||typeof post.text!=='string')return null;
    const keys=post.attachments&&post.attachments.media_keys;
    if(expectedMediaId&&(!Array.isArray(keys)||!keys.some(k=>String(k)===expectedMediaId||String(k).endsWith(`_${expectedMediaId}`))))return null;
    let text=post.text;
    // Remove only X's trailing media t.co URL when its entity expands to this
    // exact post's photo and the post reports an attachment. Never strip links.
    for(const entity of post.entities&&post.entities.urls||[]){
      const token=String(entity.url||''),expanded=String(entity.expanded_url||'');
      const photoPrefixes=[`https://x.com/Novairecito/status/${id}/photo/`,`https://twitter.com/Novairecito/status/${id}/photo/`];
      if(Array.isArray(keys)&&keys.length&&token&&photoPrefixes.some(prefix=>expanded.startsWith(prefix))&&text.endsWith(token))text=text.slice(0,-token.length).trimEnd();
    }
    return text;
  }
  const fields='expansions=attachments.media_keys&tweet.fields=author_id%2Cattachments%2Ccreated_at%2Centities&media.fields=media_key%2Curl';
  async function verifyPost(id,text,userId,expectedMediaId){const result=await request('GET',`/2/tweets/${enc(id)}?${fields}`);if(!result.data||result.data.id!==id||result.data.author_id!==userId||verifiedText(result.data,id,expectedMediaId)!==text)throw new XError('Posted item could not be verified.','verification_failed');return{id,url:`https://x.com/Novairecito/status/${id}`};}
  async function findRecent(text,userId,mediaId){const result=await request('GET',`/2/users/${enc(userId)}/tweets?max_results=5&${fields}`);const cutoff=Date.now()-10*60*1000;return(result.data||[]).find(p=>p&&verifiedText(p,String(p.id),mediaId)===text&&(!p.created_at||Date.parse(p.created_at)>=cutoff));}
  async function publish({text,png}){
    const me=await request('GET','/2/users/me');if(!me.data||me.data.username!=='Novairecito'||!/^\d+$/.test(String(me.data.id||'')))throw new XError('X account verification failed.','wrong_account');const userId=String(me.data.id);
    let existing=text?await findRecent(text,userId):null;if(existing){const out=await verifyPost(String(existing.id),text,userId);return{...out,replayed:true};}
    const upload=await request('POST','/2/media/upload',{media:Buffer.from(png).toString('base64'),media_category:'tweet_image'});const mediaId=String(upload.data&&upload.data.id||'');if(!/^\d+$/.test(mediaId))throw new XError('X media upload could not be verified.','upload_failed');
    let created;try{created=await request('POST','/2/tweets',text?{text,media:{media_ids:[mediaId]}}:{media:{media_ids:[mediaId]}});}catch(error){
      // Even a malformed error response can follow a successful create.
      // Reconcile by reading only; never retry the create request.
      // The create request may have reached X. Reconcile once; never blindly POST again.
      try{existing=await findRecent(text,userId,text?undefined:mediaId);if(existing){const out=await verifyPost(String(existing.id),text,userId,text?undefined:mediaId);return{...out,replayed:true};}}catch{}
      throw new XError('Post result is ambiguous; it was not retried. Check X before trying again.','ambiguous');
    }
    const id=String(created.data&&created.data.id||'');
    if(!/^\d+$/.test(id))throw new XError('X may have published the post, but returned no valid ID. Check X before trying again.','ambiguous');
    try{const out=await verifyPost(id,text,userId,mediaId);return{...out,replayed:false};}
    catch{throw new XError(`X accepted post ${id}, but verification failed. Check https://x.com/Novairecito/status/${id} before trying again.`,'ambiguous');}
  }
  return{publish};
}
function credentialsFromEnv(env=process.env){return{consumerKey:env.X_NOVAIRECITO_CONSUMER_KEY||'',consumerSecret:env.X_NOVAIRECITO_CONSUMER_SECRET||'',accessToken:env.X_NOVAIRECITO_ACCESS_TOKEN||'',accessTokenSecret:env.X_NOVAIRECITO_ACCESS_TOKEN_SECRET||''};}
module.exports={XError,oauthHeader,createXClient,credentialsFromEnv,configured};
