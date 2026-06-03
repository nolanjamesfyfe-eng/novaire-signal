#!/usr/bin/env node
const fs = require('fs');
const path = require('path');

const root = path.join(__dirname, '..');
const requiredFiles = [
  'index.html',
  'portfolio/index.html',
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

console.log('✅ Build guard passed: core Novaire Signal files are deployable.');
