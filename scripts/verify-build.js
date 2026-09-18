#!/usr/bin/env node
const fs = require('fs');
const path = require('path');

const root = path.join(__dirname, '..');
const requiredFiles = [
  'index.html',
  'portfolio/index.html',
  'portfolio/daily/index.html',
  'feed.json',
];

let failed = false;
for (const rel of requiredFiles) {
  const filePath = path.join(root, rel);
  if (!fs.existsSync(filePath)) {
    console.error(`❌ Build guard failed: missing ${rel}`);
    failed = true;
    continue;
  }
  const size = fs.statSync(filePath).size;
  if (size < 100) {
    console.error(`❌ Build guard failed: ${rel} is suspiciously small (${size} bytes)`);
    failed = true;
  }
}

if (failed) process.exit(1);

const portfolioPath = path.join(root, 'portfolio', 'index.html');
const html = fs.readFileSync(portfolioPath, 'utf8');
const dailyHtml = fs.readFileSync(path.join(root, 'portfolio', 'daily', 'index.html'), 'utf8');
for (const marker of ['The Daily.', 'WS TFSA', 'Kraken', 'RRSP', 'Novairecito', 'Portfolio moves · ±5%']) {
  if (!dailyHtml.includes(marker)) {
    console.error(`❌ Build guard failed: Daily is missing ${marker}`);
    process.exit(1);
  }
}

// Novaire-approved visual baseline (2026-08-16). Content and live data may
// change; these markers may change only with Novaire's explicit design approval.
const mainHtml = fs.readFileSync(path.join(root, 'index.html'), 'utf8');
const lockedDesignMarkers = [
  '--bg:#0a0a0c;--surface:#111116;--border:#1e1e26;--text:#f0eef8;--dim:#a8a4ba;--mute:#6e6a85;',
  '--gold:#b59662;--gold-dim:rgba(181,150,98,.12);--gold-mid:rgba(181,150,98,.25);',
  "--sans:'Inter',sans-serif;--serif:'Cormorant Garamond',serif;--r:6px;",
  'body{font-family:var(--sans);background:var(--bg);color:var(--text);-webkit-font-smoothing:antialiased;padding:32px 16px;font-size:18.15px;line-height:1.5}',
  '.container{max-width:720px;margin:0 auto}',
  '.card{background:var(--surface);border:1px solid var(--border);border-radius:var(--r);padding:20px;margin-bottom:14px}',
  '.footer-logo{font-family:var(--serif);font-size:1.6363636rem;font-weight:300;letter-spacing:.18em;text-transform:uppercase;color:var(--text);margin-bottom:4px}',
  '.header-brand .footer-logo,.footer .signal-brand-row{display:inline-flex;align-items:center;justify-content:center;gap:12px;white-space:nowrap;letter-spacing:0}',
  '.header-brand .signal-wordmark{display:inline-block;letter-spacing:.18em;margin-right:-.18em;color:var(--text);font-style:normal}',
  '.header-brand .signal-wordmark > span{color:var(--gold);font-style:italic}',
  '.dateline .date{font-size:.7rem;letter-spacing:.2em;text-transform:uppercase;color:var(--text)}',
  '.signal-bolt{display:inline-flex;align-items:center;justify-content:flex-start;width:1.243em;height:1.155em;text-decoration:none;transition:all .3s ease;font-size:1.1rem;color:#b59662;line-height:1}',
  '.signal-map{display:inline-flex;align-items:center;justify-content:flex-end;width:1.243em;height:1.155em;text-decoration:none;transition:all .3s ease;font-size:1.1rem;color:#b59662;line-height:1}',
  '.signal-bolt-icon{width:.738em;height:.945em;display:block;fill:currentColor;transform:translateY(.082em)}',
  '@keyframes signal-gold-shimmer{',
  '.footer .signal-bolt-icon,.footer .signal-map-icon{animation:signal-gold-shimmer 3.8s',
  'M219 44Q217 43 215 44L51 180Q49 183 51 185Q53 187 56 187L130 186Q132 186 132 188L72 289Q70 293 73 295Q76 297 83 291L239 155Q241 153 239 149Q238 147 236 147L166 148Q162 148 160 146L219 51Q222 46 219 44Z',
];
const missingDesignMarkers = lockedDesignMarkers.filter((needle) => !mainHtml.includes(needle));
const boltCount = (mainHtml.match(/class="signal-bolt-icon"/g) || []).length;
const forbiddenBoltMarkers = [
  'M32.938 15.651C32.792 15.26',
  'fill:currentColor;filter:drop-shadow(0 0 3px rgba(181,150,98,.38))',
];
const presentForbiddenBoltMarkers = forbiddenBoltMarkers.filter((needle) => mainHtml.includes(needle));

if (missingDesignMarkers.length || boltCount !== 2 || presentForbiddenBoltMarkers.length) {
  console.error('❌ Design lock failed: the approved Novaire Signal visual baseline changed.');
  for (const needle of missingDesignMarkers) console.error(`  - Missing locked marker: ${needle}`);
  if (boltCount !== 2) console.error(`  - Expected 2 approved Signal bolts; found ${boltCount}`);
  for (const needle of presentForbiddenBoltMarkers) console.error(`  - Forbidden old bolt marker returned: ${needle}`);
  console.error('  Update the design lock only after Novaire explicitly approves a visual change.');
  process.exit(1);
}

const youtubeCards = [
  'SECOND RENAISSANCE · LATEST VIDEO',
  'J.NOVAIRE · LATEST VIDEO',
  'J.NOVAIRE · LATEST SHORT',
];
function cardSegment(label) {
  const start = mainHtml.indexOf(label);
  return start >= 0 ? mainHtml.slice(start, start + 1800) : '';
}
function hasVerifiedMetrics(segment) {
  return /<b>[0-9][0-9.,KM]*<\/b> views<\/span>/.test(segment)
    && /<b>[0-9][0-9.,KM]*<\/b> likes<\/span>/.test(segment);
}
for (const label of youtubeCards) {
  if (!hasVerifiedMetrics(cardSegment(label))) {
    console.error(`❌ Build guard failed: ${label} is missing verified views or likes.`);
    process.exit(1);
  }
}
const secondRenaissanceShort = cardSegment('SECOND RENAISSANCE · LATEST SHORT');
if (!secondRenaissanceShort || (!hasVerifiedMetrics(secondRenaissanceShort) && !secondRenaissanceShort.includes('No public Shorts'))) {
  console.error('❌ Build guard failed: SECOND RENAISSANCE · LATEST SHORT is neither verified media nor an honest empty state.');
  process.exit(1);
}
const instagramCard = cardSegment('INSTAGRAM · PERSONAL LATEST VIDEO');
if (!instagramCard || (!hasVerifiedMetrics(instagramCard) && !instagramCard.includes('Instagram does not expose public'))) {
  console.error('❌ Build guard failed: personal Instagram video lacks metrics or an honest unavailable state.');
  process.exit(1);
}
for (const marker of [
  'INSTAGRAM · PERSONAL LATEST VIDEO',
  'SECOND RENAISSANCE · LATEST SHORT',
  'verified 2026-',
]) {
  if (!mainHtml.includes(marker)) {
    console.error(`❌ Build guard failed: social discovery is missing ${marker}.`);
    process.exit(1);
  }
}
if (mainHtml.includes('<strong>Latest Second Renaissance clip</strong>')) {
  console.error('❌ Build guard failed: generic YouTube clip placeholder replaced the verified cache.');
  process.exit(1);
}

const allocationRequired = [
  'data-allocation-source="google-sheet"',
  'class="allocation-legend"',
  'Google Sheet · % of Fund',
];
const allocationForbidden = [
  'Allocation awaiting Google Sheet sync.',
  'Google Sheet allocation unavailable',
];
const missingAllocation = allocationRequired.filter((needle) => !html.includes(needle));
const brokenAllocation = allocationForbidden.filter((needle) => html.includes(needle));
if (missingAllocation.length || brokenAllocation.length) {
  console.error('❌ Build guard failed: portfolio allocation is not backed by a verified Sheet snapshot.');
  for (const needle of missingAllocation) console.error(`  - Missing allocation marker: ${needle}`);
  for (const needle of brokenAllocation) console.error(`  - Forbidden offline marker present: ${needle}`);
  process.exit(1);
}

const importantButTransient = [
  'Livermore Darvis',
  'Unified Alpaca book',
  'Long · URNJ',
  'Long · EXK',
  'Long · SILJ',
  'Long · SMR',
];
const missingTransient = importantButTransient.filter((needle) => !html.includes(needle));

if (missingTransient.length) {
  console.warn('⚠️ Build guard warning: transient Alpaca markers are currently absent; allowing deploy so Signal does not spam failed-production emails.');
  for (const needle of missingTransient) console.warn(`  - ${needle}`);
}

const { spawnSync } = require('child_process');
const chartTest = spawnSync(process.execPath, [path.join(root, 'tests', 'stock-chart.mjs')], {
  cwd: root,
  encoding: 'utf8',
});
if (chartTest.status !== 0) {
  console.error('❌ Build guard failed: weekly last-close contract broke.');
  if (chartTest.stdout) process.stderr.write(chartTest.stdout);
  if (chartTest.stderr) process.stderr.write(chartTest.stderr);
  process.exit(1);
}

console.log('✅ Build guard passed: core Novaire Signal files are deployable.');
