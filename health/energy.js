export const STORAGE_KEY='novaire-health-energy-checkins-v1';
export const SCHEMA_VERSION=3;
export const dayKey=(d=new Date())=>{const y=d.getFullYear(),m=String(d.getMonth()+1).padStart(2,'0'),day=String(d.getDate()).padStart(2,'0');return `${y}-${m}-${day}`};
export function scoreAnswers(a={}){
  const clamp=(n,min,max)=>Math.min(max,Math.max(min,Number(n)||0));
  const movement=['done','planned','recovery'].includes(a.movement)?10:0;
  const total=Math.min(clamp(a.sleep,0,12)/8,1)*10+clamp(a.energy,0,10)+clamp(a.focus,0,10)+(10-clamp(a.stress,0,10))+clamp(a.calm,0,10)+clamp(a.happiness,0,10)+movement;
  return Math.round(total/70*100);
}
export function normalizeEntries(value){
  if(!Array.isArray(value))return [];
  return value.filter(e=>e&&/^\d{4}-\d{2}-\d{2}$/.test(e.date)&&Number.isFinite(Number(e.score))).map(e=>({...e,score:Math.min(100,Math.max(0,Math.round(Number(e.score)))),legacy:e.schemaVersion!==SCHEMA_VERSION}));
}
export function entriesFor(entries,view,now=new Date()){
  const days={day:1,week:7,month:30}[view]||1,cutoff=new Date(now);cutoff.setHours(0,0,0,0);cutoff.setDate(cutoff.getDate()-(days-1));
  const today=dayKey(now);
  return normalizeEntries(entries).filter(e=>e.date<=today&&new Date(`${e.date}T00:00:00`)>=cutoff);
}
const section=typeof document==='undefined'?null:document.querySelector('.energy');
if(section){
  const tabs=[...section.querySelectorAll('[role="tab"]')],segments=[...section.querySelectorAll('.energy-segment')],percent=section.querySelector('.energy-percent'),label=section.querySelector('.energy-label'),coverage=section.querySelector('.energy-coverage'),empty=section.querySelector('.energy-empty'),dialog=section.querySelector('.energy-dialog'),form=section.querySelector('.energy-form'),fields=[...form.querySelectorAll('input[type="range"]')];
  let view='day';
  const read=()=>{try{return normalizeEntries(JSON.parse(localStorage.getItem(STORAGE_KEY)||'[]'))}catch{return[]}};
  const stateFor=score=>score>=70?{color:'#48e0b1',text:'STEADY  /  PACE YOURSELF'}:score>=40?{color:'#ffc45d',text:'LIMITED  /  PROTECT YOUR PACE'}:{color:'#ff6b62',text:'LOW  /  RECOVERY FIRST'};
  function render(){
    const days={day:1,week:7,month:30}[view],entries=entriesFor(read(),view);
    if(!entries.length){section.style.setProperty('--energy-state','#48e0b1');segments.forEach(s=>s.classList.remove('lit'));percent.textContent='—';label.textContent='NO CHECK-IN DATA';coverage.textContent=view==='day'?'Nothing logged today.':`0 of ${days} days logged.`;empty.hidden=false;document.dispatchEvent(new CustomEvent('health:checkin',{detail:null}));return}
    const score=Math.round(entries.reduce((sum,e)=>sum+e.score,0)/entries.length),state=stateFor(score),lit=score===0?0:Math.max(1,Math.round(score/10));
    section.style.setProperty('--energy-state',state.color);segments.forEach((s,i)=>s.classList.toggle('lit',i<lit));percent.textContent=`${score}%`;label.textContent=state.text;coverage.textContent=view==='day'?'Today’s self-report wellbeing.':`${entries.length} of ${days} days logged · average of recorded check-ins only.`;empty.hidden=true;document.dispatchEvent(new CustomEvent('health:checkin',{detail:view==='day'?entries[entries.length-1]:null}));
  }
  tabs.forEach(tab=>tab.addEventListener('click',()=>{tabs.forEach(t=>t.setAttribute('aria-selected',String(t===tab)));view=tab.dataset.view;render()}));
  const todayEntry=()=>read().find(e=>e.date===dayKey());
  function updateField(input){const value=Number(input.value),max=Number(input.max),visual=input.name==='stress'?max-value:value;input.style.setProperty('--range-color',`hsl(${Math.round(visual/max*120)} 78% 54%)`);form.querySelector(`output[for="${input.id}"]`).value=input.name==='sleep'?`${value} h`:`${value} / 10`}
  function openCheckin(){
    const saved=todayEntry(),a=saved?.answers||{},legacyScale=saved?.scaleMax===5||(!saved?.scaleMax&&Math.max(Number(a.energy)||0,Number(a.focus)||0,Number(a.stress)||0)<=5);
    fields.forEach(input=>{let value=a[input.name];if(legacyScale&&['energy','focus','stress'].includes(input.name)&&Number.isFinite(Number(value)))value=Number(value)*2;if(!Number.isFinite(Number(value)))value=input.name==='sleep'?8:5;input.value=value;updateField(input)});
    const movement=a.movement||'planned';const radio=form.querySelector(`input[name="movement"][value="${movement}"]`)||form.querySelector('input[name="movement"][value="planned"]');radio.checked=true;form.querySelector('.energy-feedback').textContent='';dialog.showModal();
  }
  section.querySelector('.energy-checkin-open').addEventListener('click',openCheckin);section.querySelector('.energy-close').addEventListener('click',()=>dialog.close());fields.forEach(input=>{updateField(input);input.addEventListener('input',()=>updateField(input))});
  form.addEventListener('submit',event=>{event.preventDefault();const answers=Object.fromEntries(fields.map(i=>[i.name,Number(i.value)]));answers.movement=form.elements.movement.value;const score=scoreAnswers(answers),entries=read().filter(e=>e.date!==dayKey());entries.push({date:dayKey(),schemaVersion:SCHEMA_VERSION,scaleMax:10,score,answers});entries.sort((a,b)=>a.date.localeCompare(b.date));localStorage.setItem(STORAGE_KEY,JSON.stringify(entries));form.querySelector('.energy-feedback').textContent=`Saved: ${score}% · ${answers.movement==='done'?'workout done':answers.movement==='planned'?'workout planned':answers.movement==='recovery'?'recovery day':'no movement plan'}.`;view='day';tabs.forEach(t=>t.setAttribute('aria-selected',String(t.dataset.view==='day')));render();setTimeout(()=>dialog.close(),900)});
  window.__HEALTH_ENERGY__={scoreAnswers,normalizeEntries,entriesFor,read,render};render();
}
