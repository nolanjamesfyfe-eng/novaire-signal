#!/usr/bin/env node
const fs = require('fs');
const path = require('path');

const portfolioPath = path.join(__dirname, '..', 'portfolio', 'index.html');
const html = fs.readFileSync(portfolioPath, 'utf8');

const required = [
  'Livermore Darvis',
  'Unified Alpaca book',
  'Long · URNJ',
  'Long · EXK',
  'Long · SILJ',
  'Long · SMR',
];

const missing = required.filter((needle) => !html.includes(needle));
if (missing.length) {
  console.error('❌ Build guard failed: portfolio/index.html is missing Alpaca section markers:');
  for (const needle of missing) console.error(`  - ${needle}`);
  process.exit(1);
}

console.log('✅ Build guard passed: Alpaca portfolio section present.');
