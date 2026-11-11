import assert from 'node:assert/strict';
import { parseUranium, parseYahooFuture, YAHOO_COMMODITIES, EXPECTED_SYMBOLS } from '../api/commodities.js';

// Trading Economics verb drift: "fell to" broke the old "at"-only regex (2026-11-11).
const te = '<meta name="description" content="Uranium fell to 90.95 USD/Lbs on November 10, 2026, down 0.49% from the previous day.">'
  + '<p>Uranium is expected to trade at 92.50 USD/LBS by the end of this quarter</p>';
let u = parseUranium(te);
assert.equal(u.price, 90.95, 'must read the dated print, never the forecast');
assert.equal(u.change, -0.49);
assert.equal(u.quoteTime.slice(0, 10), '2026-11-10');
for (const verb of ['rose to', 'increased to', 'remained at', 'traded at', 'decreased to', 'fell to']) {
  u = parseUranium(`Uranium ${verb} 88.10 USD/Lbs on March 3, 2027, up 1.2% from the previous day`);
  assert.equal(u.price, 88.10, verb);
  assert.equal(u.change, 1.2, verb);
}
assert.equal(parseUranium('Uranium is expected to trade at 92.50 USD/LBS by the end of this quarter'), null);

// Yahoo: live meta price beats the last bar; null bars dropped; diesel gal -> bbl.
const s = parseYahooFuture({chart: {result: [{meta: {regularMarketPrice: 53.025, regularMarketTime: 1794393057},
  timestamp: [1, 2, 3, 4], indicators: {quote: [{close: [52.5, 51.2, 53.0, null]}]}}]}}, 'SILVER', YAHOO_COMMODITIES.SILVER);
assert.equal(s.price, 53.025);
assert.equal(s.previous, 51.2);
const d = parseYahooFuture({chart: {result: [{meta: {regularMarketPrice: 4.2}, timestamp: [1, 2], indicators: {quote: [{close: [4.0, 4.1]}]}}]}}, 'DIESEL', YAHOO_COMMODITIES.DIESEL);
assert.ok(Math.abs(d.price - 176.4) < 1e-9 && Math.abs(d.previous - 168) < 1e-9);
assert.deepEqual([...EXPECTED_SYMBOLS].sort(), ['COPPER', 'DIESEL', 'GOLD', 'SILVER', 'URANIUM_SPOT', 'WTI']);
console.log('commodities parsers: ok');
