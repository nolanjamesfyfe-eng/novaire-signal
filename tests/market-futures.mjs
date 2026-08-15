import assert from 'node:assert/strict';
import { parseYahooChart } from '../api/market-futures.js';

const payload = {
  chart: {
    result: [{
      meta: { regularMarketTime: 1786739967 },
      timestamp: [1786455000, 1786541400, 1786627800, 1786714200],
      indicators: { quote: [{ close: [23250, null, 23400, 23517] }] },
    }],
    error: null,
  },
};

const quote = parseYahooChart(payload);
assert.equal(quote.price, 23517);
assert.equal(quote.previous, 23400);
assert.equal(quote.change, 0.5);
assert.equal(quote.source, 'Yahoo Finance');
assert.equal(quote.period, 'futures session');
assert.equal(quote.quoteTime, '2026-08-14T20:39:27.000Z');
console.log('market futures parser: ok');
