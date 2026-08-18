import assert from 'node:assert/strict';
import { parseRbobCrack } from '../api/commodities.js';

const rbob = {chart:{result:[{timestamp:[1786507200,1786593600,1786680000],indicators:{quote:[{close:[2.5,2.6,2.7]}]}}]}};
const wti = {chart:{result:[{timestamp:[1786507248,1786593648,1786680048],indicators:{quote:[{close:[80,82,84]}]}}]}};
const quote = parseRbobCrack(rbob, wti);
assert.equal(quote.symbol, 'RBOB_CRACK');
assert.ok(Math.abs(quote.price - 29.4) < 1e-9);
assert.ok(Math.abs(quote.previous - 27.2) < 1e-9);
assert.ok(Math.abs(quote.change - ((29.4 - 27.2) / 27.2 * 100)) < 1e-9);
assert.equal(quote.formula, 'RBOB × 42 − WTI');
console.log('commodities crack parser: ok');
