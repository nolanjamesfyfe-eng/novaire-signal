const root=document.querySelector('.brain-overlay');
if(root){
  const copy={energy:['Energy','How physiologically energetic you reported feeling.'],focus:['Focus / clarity','How readily you can get to work and sustain a Pomodoro.'],stress:['Low stress','Reverse-scored from stress: 0 stress earns 10/10.'],calm:['Calm','How content, rested and low in felt stress you feel.'],happiness:['Happiness','Your self-reported contentment versus frustration.']};
  let latest=null;
  function paint(entry){latest=entry?.answers||null;root.classList.toggle('has-data',!!latest);for(const path of root.querySelectorAll('[data-region]')){const key=path.dataset.region,value=latest?(key==='stress'?10-Number(latest.stress):Number(latest[key])):0;path.style.setProperty('--region-level',Math.max(0,Math.min(1,value/10)))} }
  document.addEventListener('health:checkin',e=>paint(e.detail));
  root.querySelectorAll('button').forEach(button=>button.addEventListener('click',()=>{const key=button.dataset.brainRegion,[title,description]=copy[key],raw=latest?.[key],score=latest?(key==='stress'?10-Number(raw):Number(raw)):null,pop=root.querySelector('.brain-popover');pop.innerHTML=`<b>${title}</b><span>${score==null?'No check-in yet':`${score}/10 contribution`}</span><small>${description}</small>`;pop.hidden=false;root.querySelectorAll('button').forEach(b=>b.setAttribute('aria-pressed',String(b===button)))}));
  paint(null);
}
