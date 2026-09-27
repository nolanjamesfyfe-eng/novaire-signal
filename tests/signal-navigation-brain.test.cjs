const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const root=path.join(__dirname,'..');
const pages=['index.html','map/index.html','health/index.html'];
for(const file of pages)test(`${file} exposes balanced Signal navigation`,()=>{
  const html=fs.readFileSync(path.join(root,file),'utf8');
  const row=html.match(/<div class="signal-brand-row"[^>]*>(.*?)<\/div>/s)?.[1]||'';
  assert.ok(row,'brand row missing');
  const order=['signal-map','signal-wordmark','signal-bolt','signal-health'].map(name=>row.indexOf(name));
  assert.ok(order.every(i=>i>=0),`missing navigation icon in ${file}`);
  assert.deepEqual(order,[...order].sort((a,b)=>a-b),`navigation order wrong in ${file}`);
  assert.match(row,/href="(?:\/health\/)?#energy-checkin"|href="\/health\/#energy-checkin"/);
  assert.match(row,/viewBox="45 38 200 264"/,'canonical traced bolt changed');
});
test('canonical navigation keeps equal icon boxes, battery pulse and reduced-motion fallback',()=>{
  const source=fs.readFileSync(path.join(root,'signal_brand.py'),'utf8');
  assert.match(source,/width:1\.243em;height:1\.155em;margin-left:0/);
  assert.match(source,/signal-health-icon\{animation:signal-gold-shimmer/);
  assert.match(source,/@media\(prefers-reduced-motion:reduce\).*signal-health-icon/s);
});
test('brain is explicitly illustrative, no-data honest, and synapses require check-in plus zoom',()=>{
  const html=fs.readFileSync(path.join(root,'health/index.html'),'utf8');
  const css=fs.readFileSync(path.join(root,'health/brain-overlay.css'),'utf8');
  const js=fs.readFileSync(path.join(root,'health/brain-overlay.js'),'utf8');
  assert.match(html,/SYMBOLIC SELF-REPORT MAP · NOT MEASURED BRAIN ACTIVITY/);
  assert.match(html,/class="synapses"/);
  assert.match(css,/\.brain-overlay \.synapses\{opacity:0/);
  assert.match(css,/\.brain-overlay\.zoom-detail\.has-data \.synapses/);
  for(const input of ['sleep','energy','focus','stress','calm','happiness','movement']) assert.ok(js.includes(input),`missing ${input} integration`);
  assert.match(js,/distance<=14/);
});
