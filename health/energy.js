const STORAGE_KEY='novaire-health-energy-checkins-v1';
const section=document.querySelector('.energy');
if(section){
  const tabs=[...section.querySelectorAll('[role="tab"]')];
  const segments=[...section.querySelectorAll('.energy-segment')];
  const percent=section.querySelector('.energy-percent');
  const label=section.querySelector('.energy-label');
  const coverage=section.querySelector('.energy-coverage');
  const empty=section.querySelector('.energy-empty');
  const dialog=section.querySelector('.energy-dialog');
  const form=section.querySelector('.energy-form');
  const fields=[...form.querySelectorAll('input[type="range"]')];
  let view='day';
  const read=()=>{try{const value=JSON.parse(localStorage.getItem(STORAGE_KEY)||'[]');return Array.isArray(value)?value:[]}catch{return[]}};
  const dayKey=(d=new Date())=>{const y=d.getFullYear(),m=String(d.getMonth()+1).padStart(2,'0'),day=String(d.getDate()).padStart(2,'0');return `${y}-${m}-${day}`};
  const daysFor={day:1,week:7,month:30};
  function stateFor(score){if(score>=70)return{color:'#48e0b1',text:'STEADY  /  PACE YOURSELF'};if(score>=40)return{color:'#ffc45d',text:'LIMITED  /  PROTECT YOUR PACE'};return{color:'#ff6b62',text:'LOW  /  RECOVERY FIRST'}}
  function render(){
    const days=daysFor[view],cutoff=new Date();cutoff.setHours(0,0,0,0);cutoff.setDate(cutoff.getDate()-(days-1));
    const entries=read().filter(e=>{const d=new Date(`${e.date}T00:00:00`);return d>=cutoff&&Number.isFinite(e.score)});
    if(!entries.length){section.style.setProperty('--energy-state','#48e0b1');segments.forEach(s=>s.classList.remove('lit'));percent.textContent='—';label.textContent='NO CHECK-IN DATA';coverage.textContent=view==='day'?'Nothing logged today.':`0 of ${days} days logged.`;empty.hidden=false;return}
    const score=Math.round(entries.reduce((sum,e)=>sum+e.score,0)/entries.length),state=stateFor(score),lit=Math.max(1,Math.round(score/10));
    section.style.setProperty('--energy-state',state.color);segments.forEach((s,i)=>s.classList.toggle('lit',i<lit));percent.textContent=`${score}%`;label.textContent=state.text;coverage.textContent=view==='day'?'Today’s self-report estimate.':`${entries.length} of ${days} days logged · average of available check-ins.`;empty.hidden=true;
  }
  tabs.forEach(tab=>tab.addEventListener('click',()=>{tabs.forEach(t=>t.setAttribute('aria-selected',String(t===tab)));view=tab.dataset.view;render()}));
  section.querySelector('.energy-checkin-open').addEventListener('click',()=>dialog.showModal());
  section.querySelector('.energy-close').addEventListener('click',()=>dialog.close());
  fields.forEach(input=>input.addEventListener('input',()=>{form.querySelector(`output[for="${input.id}"]`).value=input.value}));
  form.addEventListener('submit',event=>{event.preventDefault();const values=Object.fromEntries(fields.map(i=>[i.name,Number(i.value)]));const score=Math.round(((values.energy+values.focus+(6-values.stress)+(6-values.soreness))/20)*100);const entries=read().filter(e=>e.date!==dayKey());entries.push({date:dayKey(),score,answers:values});localStorage.setItem(STORAGE_KEY,JSON.stringify(entries));form.querySelector('.energy-feedback').textContent='Saved on this browser only.';view='day';tabs.forEach(t=>t.setAttribute('aria-selected',String(t.dataset.view==='day')));render();setTimeout(()=>dialog.close(),650)});
  render();
}
