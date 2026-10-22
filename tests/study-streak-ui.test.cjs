'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const html = fs.readFileSync(path.join(__dirname, '..', 'index.html'), 'utf8');
function cardSegment() {
  const start = html.indexOf('<section class="card anki-quick-row"');
  const end = html.indexOf('</section>', start);
  return start >= 0 && end >= 0 ? html.slice(start, end) : '';
}

test('generated Anki control is one compact direct-link row with truthful copy', () => {
  const card = cardSegment();
  assert.ok(card, 'Anki row is missing');
  assert.match(card, /id="daily-study"/);
  assert.match(card, /<strong>Anki<\/strong>/);
  assert.match(card, /href="https:\/\/ankiweb\.net\/decks\/"/);
  assert.match(card, /target="_blank"/);
  assert.match(card, /Open AnkiWeb/);
  assert.match(card, /click days only/);
  assert.match(card, /Deck completion is not verified/);
  assert.match(card, /id="anki-streak-status"/);
  assert.match(card, /id="anki-sync-status"/);
  assert.match(card, /id="anki-sync-control"/);
  assert.doesNotMatch(card, /Click streak locked|Unlock private sync|Your decks, one deliberate click away|Daily Study/);
});

test('generated behavior records locally before optional private sync without blocking navigation', () => {
  assert.match(html, /LOCAL_KEY='nv_anki_click_dates_v1'/);
  assert.match(html, /writeLocal\(\[\.\.\.memoryDates,today\]\);localRender\(\)/);
  assert.match(html, /ankiLink\.addEventListener\('click'/);
  assert.match(html, /fetch\(STUDY_API,\{method:'POST'/);
  assert.match(html, /action,localDates:memoryDates/);
  assert.doesNotMatch(html, /preventDefault\(\).*recordClick/s);
  assert.match(html, /credentials:'same-origin'/);
  assert.match(html, /keepalive:action==='click'/);
  assert.match(html, /This tab only · storage blocked/);
  assert.match(html, /Saved locally · sync offline/);
});

test('warning semantics separate streak from completed missed days and respect reduced motion', () => {
  assert.match(html, /missed>=3\?'urgent':'warn'/);
  assert.match(html, /day'\+\(missed===1\?'':'s'\)\+' missed · restart today'/);
  assert.match(html, /streak · clicked today/);
  assert.match(html, /@keyframes anki-warn-pulse/);
  assert.match(html, /@keyframes anki-urgent-pulse/);
  assert.match(html, /prefers-reduced-motion:reduce\)\{\.anki-streak-status/);
  assert.match(html, /animation:none;opacity:1/);
});

test('oversized legacy lock UI and recent-day chip wall are absent', () => {
  for (const forbidden of ['anki-study-accordion', 'anki-accordion-cue', 'anki-recent-days', 'anki-day[data-status', 'Click streak locked', 'Unlock sync']) {
    assert.equal(html.includes(forbidden), false, `legacy marker returned: ${forbidden}`);
  }
  assert.match(html, /\.card\.anki-quick-row\{position:relative;display:grid/);
  assert.match(html, /padding:11px 13px/);
});
