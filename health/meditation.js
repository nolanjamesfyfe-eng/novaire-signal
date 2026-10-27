(()=>{const fmt=t=>{t=Math.max(0,Math.floor(t||0));return Math.floor(t/60)+':'+String(t%60).padStart(2,'0')};
const tracks=[...document.querySelectorAll('.meditation-track')];
tracks.forEach(card=>{const a=card.querySelector('audio'),b=card.querySelector('.meditation-play'),bar=card.querySelector('.meditation-progress'),fill=bar.querySelector('i'),time=card.querySelector('time'),total=Number(card.dataset.length)*60,label=card.dataset.length+'-minute meditation';
const sync=()=>{const d=isFinite(a.duration)&&a.duration?a.duration:total;fill.style.width=(a.currentTime/d*100)+'%';time.textContent=fmt(a.currentTime)+' / '+fmt(d)};
const state=p=>{card.classList.toggle('playing',p);b.setAttribute('aria-pressed',String(p));b.setAttribute('aria-label',(p?'Pause ':'Play ')+label)};
b.addEventListener('click',()=>{if(a.paused){tracks.forEach(o=>{const oa=o.querySelector('audio');if(oa!==a&&!oa.paused)oa.pause()});a.play().catch(()=>state(false))}else a.pause()});
a.addEventListener('play',()=>state(true));a.addEventListener('pause',()=>state(false));a.addEventListener('ended',()=>{state(false);a.currentTime=0;sync()});a.addEventListener('timeupdate',sync);a.addEventListener('loadedmetadata',sync);
bar.addEventListener('click',e=>{const r=bar.getBoundingClientRect(),d=isFinite(a.duration)&&a.duration?a.duration:total;a.currentTime=Math.min(d,Math.max(0,(e.clientX-r.left)/r.width*d));sync()});});})();
