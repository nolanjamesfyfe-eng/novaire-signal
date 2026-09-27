(function (root, factory) {
  const api = factory(root);
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.HealthInjuryJournal = api;
})(typeof window === 'undefined' ? null : window, function (win) {
  'use strict';
  const SCHEMA = 'novaire.health.injury-journal';
  const VERSION = 1;
  const STORAGE_KEY = 'novaire-health-injury-journal-v1';
  const clean = () => ({ schema: SCHEMA, version: VERSION, injuries: [], daily: [] });
  const text = (v, max=500) => typeof v === 'string' && v.length <= max;
  const date = v => text(v,10) && /^\d{4}-\d{2}-\d{2}$/.test(v);
  const timestamp = v => text(v,35) && !Number.isNaN(Date.parse(v));
  const finite = v => Number.isFinite(v);
  function validPoint(p) { return p && finite(p.x) && finite(p.y) && finite(p.z) && text(p.structureKey,160) && text(p.structureName,200) && ['muscle','bone'].includes(p.layer); }
  function validInjury(x) { return x && text(x.id,100) && timestamp(x.createdAt) && ['ongoing','resolved'].includes(x.status) && Number.isInteger(x.severity) && x.severity>=0 && x.severity<=10 && date(x.onset) && text(x.mechanism,300) && text(x.note,1200) && validPoint(x.point); }
  function validDay(x) { return x && text(x.id,100) && date(x.date) && finite(x.sleepHours) && x.sleepHours>=0 && x.sleepHours<=24 && Number.isInteger(x.sleepQuality) && x.sleepQuality>=1 && x.sleepQuality<=5 && text(x.training,300) && typeof x.lateMeal==='boolean' && (x.mealTime==='' || (text(x.mealTime,5) && /^([01]\d|2[0-3]):[0-5]\d$/.test(x.mealTime))); }
  function validateJournal(value) {
    if (!value || value.schema!==SCHEMA || value.version!==VERSION || !Array.isArray(value.injuries) || !Array.isArray(value.daily) || !value.injuries.every(validInjury) || !value.daily.every(validDay)) return {ok:false,error:'Invalid or unsupported injury journal JSON.'};
    return {ok:true,value:JSON.parse(JSON.stringify(value))};
  }
  function describeAssociations(days) {
    if (!Array.isArray(days) || days.length < 3) return 'Not enough logged days to describe an association yet.';
    return 'Logged sleep, training and meal timing can be compared with soreness entries as an association only; this journal does not establish causes.';
  }
  function extractRecordInjuries(record) {
    if (!record || typeof record!=='object') return [];
    const nested = [record.injuries, record.injuryHistory, record.lifelongInjuries].find(Array.isArray) || [];
    const candidates = record.region && text(record.label,200) ? [record, ...nested] : nested;
    return candidates.filter(x=>x && typeof x==='object' && text(x.label,200)).map(x=>({id:text(x.id,100)?x.id:`record-${x.region||x.label}`,label:x.label,region:text(x.region,100)?x.region:'',status:['ongoing','resolved'].includes(x.status)?x.status:'',point:validPoint(x.point)?x.point:null,source:'authenticated-record'}));
  }
  function mount() {
    if (!win || !win.document || win.document.querySelector('[data-injury-journal]')) return;
    const d=win.document, panel=d.createElement('aside'); panel.className='injury-journal';panel.dataset.injuryJournal='';panel.hidden=true;
    panel.innerHTML=`<header><div><p class="injury-journal__kicker">PRIVATE · LOCAL JOURNAL</p><h2>Injury & recovery journal</h2></div><button type="button" data-journal-close aria-label="Close injury journal">×</button></header>
      <p class="injury-journal__privacy">Visible only after your private health record is unlocked. Journal entries stay in this browser’s local storage; they are not sent to or stored by the server.</p>
      <div class="injury-journal__actions"><button type="button" data-log-point>LOG SORENESS POINT</button><button type="button" data-export>EXPORT JSON</button><label>IMPORT JSON<input type="file" accept="application/json" data-import></label></div>
      <p class="injury-journal__mode" role="status">Choose “Log soreness point,” then tap the exact place on the 3D body.</p>
      <form data-injury-form hidden><h3>Point details</h3><p data-point-label></p><fieldset><legend>Is this the same injury or a new injury?</legend><label><input type="radio" name="relationship" value="new" checked> New injury</label><label><input type="radio" name="relationship" value="same"> Same / recurring injury</label></fieldset><label>Severity (0–10)<input name="severity" type="number" min="0" max="10" value="3" required></label><label>Onset<input name="onset" type="date" required></label><label>Mechanism<input name="mechanism" maxlength="300" placeholder="What happened?" required></label><label>Note<textarea name="note" maxlength="1200"></textarea></label><label>Status<select name="status"><option value="ongoing">Ongoing</option><option value="resolved">Resolved</option></select></label><button type="submit">SAVE LOCAL POINT</button></form>
      <section><h3>Lifelong injuries & daily points</h3><div data-injuries></div></section>
      <form data-daily-form><h3>Daily context</h3><label>Date<input name="date" type="date" required></label><label>Sleep hours<input name="sleepHours" type="number" min="0" max="24" step="0.25" required></label><label>Sleep quality (1–5)<input name="sleepQuality" type="number" min="1" max="5" required></label><label>Training<input name="training" maxlength="300" placeholder="Session, recovery, or rest" required></label><label><input name="lateMeal" type="checkbox"> Late meal</label><label>Meal time<input name="mealTime" type="time"></label><button type="submit">SAVE DAILY CONTEXT</button></form><p data-association></p><p data-journal-feedback role="status"></p>`;
    (d.querySelector('.stage')||d.querySelector('main')||d.body).append(panel);
    const open=d.createElement('button');open.type='button';open.className='injury-journal__open';open.textContent='INJURY JOURNAL';open.hidden=true;(d.querySelector('.stage')||d.body).append(open);
    let unlocked=false,data=clean(),pending=null,recordInjuries=[];
    const q=s=>panel.querySelector(s), feedback=m=>q('[data-journal-feedback]').textContent=m;
    function read(){try{const parsed=validateJournal(JSON.parse(win.localStorage.getItem(STORAGE_KEY)||'null'));data=parsed.ok?parsed.value:clean();}catch{data=clean();}}
    function persist(){win.localStorage.setItem(STORAGE_KEY,JSON.stringify(data));render();}
    function pins(){if(!unlocked)return;win.dispatchEvent(new CustomEvent('health:journal-points-ready',{detail:{points:data.injuries.map(x=>({id:x.id,label:x.point.structureName,severity:x.severity,status:x.status,point:x.point})),recordInjuries}}));}
    function render(){if(!unlocked)return;const all=[...recordInjuries.map(x=>`<article><b>${escapeHtml(x.label)}</b><small>AUTHENTICATED HEALTH RECORD${x.status?` · ${x.status.toUpperCase()}`:''}</small></article>`),...data.injuries.map(x=>`<article><b>${escapeHtml(x.point.structureName)}</b><span>${x.severity}/10 · ${escapeHtml(x.status)} · ${escapeHtml(x.onset)}</span><small>LOCAL ONLY · ${escapeHtml(x.mechanism)}</small></article>`)];q('[data-injuries]').innerHTML=all.join('')||'<p>No injury history is available in the authenticated record and no local points are logged.</p>';q('[data-association]').textContent=describeAssociations(data.daily);pins();}
    function escapeHtml(v){const el=d.createElement('span');el.textContent=String(v);return el.innerHTML;}
    win.addEventListener('health:record-ready',e=>{unlocked=true;recordInjuries=extractRecordInjuries(e.detail);read();panel.hidden=false;open.hidden=false;render()});
    win.addEventListener('health:record-cleared',()=>{unlocked=false;data=clean();pending=null;recordInjuries=[];panel.hidden=true;open.hidden=true;q('[data-injury-form]').hidden=true;win.dispatchEvent(new CustomEvent('health:journal-points-cleared'))});
    win.addEventListener('health:point-selected',e=>{if(!unlocked)return;pending=e.detail;q('[data-point-label]').textContent=`${pending.structureName} · exact 3D surface point`;q('[data-injury-form]').hidden=false;feedback('Point captured. Add the injury details.');});
    open.onclick=()=>panel.hidden=false;q('[data-journal-close]').onclick=()=>panel.hidden=true;
    q('[data-log-point]').onclick=()=>{win.dispatchEvent(new CustomEvent('health:log-mode-changed',{detail:{active:true}}));feedback('Log soreness mode is active. Tap the exact place on the 3D body.');};
    q('[data-injury-form]').onsubmit=e=>{e.preventDefault();if(!pending)return;const f=new FormData(e.currentTarget),now=new Date();data.injuries.push({id:`local-${now.getTime()}`,createdAt:now.toISOString(),relationship:f.get('relationship'),status:f.get('status'),severity:Number(f.get('severity')),onset:f.get('onset'),mechanism:String(f.get('mechanism')),note:String(f.get('note')),point:pending});const check=validateJournal(data);if(!check.ok){feedback(check.error);return}persist();pending=null;e.currentTarget.hidden=true;win.dispatchEvent(new CustomEvent('health:log-mode-changed',{detail:{active:false}}));feedback('Saved locally in this browser.');};
    const today=new Date().toISOString().slice(0,10);q('[data-daily-form] [name=date]').value=today;
    q('[data-daily-form]').onsubmit=e=>{e.preventDefault();const f=new FormData(e.currentTarget),entry={id:`day-${f.get('date')}`,date:f.get('date'),sleepHours:Number(f.get('sleepHours')),sleepQuality:Number(f.get('sleepQuality')),training:String(f.get('training')),lateMeal:f.get('lateMeal')==='on',mealTime:String(f.get('mealTime'))};data.daily=data.daily.filter(x=>x.date!==entry.date);data.daily.push(entry);const check=validateJournal(data);if(!check.ok){feedback(check.error);return}persist();feedback('Daily context saved locally. Associations are descriptive, never causal.');};
    q('[data-export]').onclick=()=>{const blob=new Blob([JSON.stringify(data,null,2)],{type:'application/json'}),a=d.createElement('a');a.href=URL.createObjectURL(blob);a.download='novaire-health-journal.json';a.click();URL.revokeObjectURL(a.href);feedback('Exported local journal JSON.');};
    q('[data-import]').onchange=async e=>{try{const result=validateJournal(JSON.parse(await e.target.files[0].text()));if(!result.ok)throw new Error(result.error);data=result.value;persist();feedback('Imported validated local journal JSON.');}catch(err){feedback(err.message||'Import failed.')}finally{e.target.value='';}};
  }
  if(win){if(win.document.readyState==='loading')win.document.addEventListener('DOMContentLoaded',mount,{once:true});else mount();}
  return {SCHEMA,VERSION,STORAGE_KEY,validateJournal,describeAssociations,extractRecordInjuries,mount};
});
