'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const html = fs.readFileSync(path.join(__dirname, '..', 'index.html'), 'utf8');

test('generated Daily Study card preserves the approved Option E anchor design', () => {
  const id = html.indexOf('id="daily-study"');
  assert.ok(id >= 0, 'Daily Study anchor is missing');
  const start = html.lastIndexOf('<details', id);
  const end = html.indexOf('</details>', id);
  const card = html.slice(start, end);
  assert.match(card, /class="card signal-accordion anki-study-accordion"/);
  assert.match(card, /🗂 Daily Study/);
  assert.match(card, /Your decks, one deliberate click away\./);
  assert.match(card, /href="https:\/\/ankiweb\.net\/decks\/"/);
  assert.match(card, /target="_blank"/);
  assert.match(card, /id="anki-streak-status"/);
  assert.match(card, /id="anki-today-status"/);
  assert.match(card, /id="anki-recent-days"/);
  assert.match(card, /id="anki-sync-form"/);
});

test('generated behavior records clicks only from anchor activation and reports failures honestly', () => {
  assert.match(html, /ankiLink\.addEventListener\('click'/);
  assert.match(html, /fetch\(STUDY_API,\{method:'POST'/);
  assert.doesNotMatch(html, /preventDefault\(\).*STUDY_API/s);
  assert.match(html, /AnkiWeb opened · click not recorded/);
  assert.match(html, /credentials:'same-origin'/);
  assert.match(html, /keepalive:true/);
});

test('collapsed Daily Study reminder has an explicit compact geometry and keyboard focus ring', () => {
  assert.match(html, /\.card\.anki-study-accordion\{box-sizing:border-box;padding:0;/);
  assert.match(html, /\.anki-study-accordion:not\(\[open\]\)\{height:42px;min-height:42px\}/);
  assert.match(html, /\.anki-study-accordion>summary\{height:42px;min-height:42px;box-sizing:border-box;padding:8px 14px\}/);
  assert.match(html, /\.anki-study-accordion>summary:focus\{outline:none\}/);
  assert.match(html, /\.anki-study-accordion>summary:focus-visible\{outline:2px solid #9db8ff;outline-offset:-2px\}/);
  assert.match(html, /\.anki-study-accordion:not\(\[open\]\),\.anki-study-accordion>summary\{height:40px;min-height:40px\}/);
});
