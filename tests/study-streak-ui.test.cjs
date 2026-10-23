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
  assert.match(card, />Anki ↗<\/a>/);
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
  assert.match(html, /missed>=3\?'urgent':missed===2\?'positive':'warn'/);
  assert.match(html, /day'\+\(missed===1\?'':'s'\)\+' missed · restart today'/);
  assert.match(html, /streak · clicked today/);
  assert.match(html, /@keyframes anki-positive-pulse/);
  assert.match(html, /@keyframes anki-warn-pulse/);
  assert.match(html, /@keyframes anki-urgent-pulse/);
  assert.match(html, /prefers-reduced-motion:reduce\)\{\.anki-streak-status/);
  assert.match(html, /animation:none;opacity:1/);
});

test('Anki positive states reuse the exact market gain green and glow palette', () => {
  assert.match(html, /\.positive\{color:#56f2b1;animation:finance-green-pulse/);
  assert.match(html, /\.anki-streak-status\[data-tone="positive"\]\{color:#56f2b1;animation:anki-positive-pulse 3\.8s/);
  assert.match(html, /@keyframes anki-positive-pulse\{0%,100%\{text-shadow:0 0 4px rgba\(86,242,177,\.45\),0 0 11px rgba\(86,242,177,\.20\);filter:brightness\(1\)\}50%\{text-shadow:0 0 7px rgba\(86,242,177,\.92\),0 0 19px rgba\(86,242,177,\.48\),0 0 30px rgba\(86,242,177,\.18\);filter:brightness\(1\.18\)\}\}/);
  assert.doesNotMatch(html, /\.anki-streak-status\[data-tone="positive"\]\{color:#438a63/);
});

test('unknown local history is coverage-bounded and the visible link is precisely half-size', () => {
  assert.match(html, /META_KEY='nv_anki_click_coverage_v1'/);
  assert.match(html, /firstObserved/);
  assert.match(html, /canonical/);
  assert.match(html, /Start today/);
  assert.match(html, /Not synced/);
  assert.match(html, /width:60\.6171875px;height:16\.15767045px/);
  assert.match(html, /width:49\.0078125px;height:14\.8125px/);
  assert.match(html, /\.anki-panel-link::after\{content:"";position:absolute/);
  assert.match(html, /height:44\.1px/);
});

test('oversized legacy lock UI and recent-day chip wall are absent', () => {
  for (const forbidden of ['anki-study-accordion', 'anki-accordion-cue', 'anki-recent-days', 'anki-day[data-status', 'Click streak locked', 'Unlock sync']) {
    assert.equal(html.includes(forbidden), false, `legacy marker returned: ${forbidden}`);
  }
  assert.match(html, /\.card\.anki-quick-row\{position:relative;display:grid/);
  assert.match(html, /padding:11px 13px/);
});
