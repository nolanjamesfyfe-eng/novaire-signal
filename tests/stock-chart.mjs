import assert from 'node:assert/strict';
import { aggregateCompletedWeeks } from '../api/stock-chart.js';

const start = Date.UTC(2025, 0, 6, 16) / 1000;
const timestamps = Array.from({ length: 45 }, (_, i) => start + i * 7 * 86400);
const values = timestamps.map((_, i) => i + 1);
const payload = { chart: { result: [{
  meta: { currency: 'CAD' },
  timestamp: timestamps,
  indicators: { quote: [{
    open: values,
    high: values.map(v => v + 1),
    low: values.map(v => v - 1),
    close: values.map(v => v + 0.5),
    volume: values.map(v => v * 100),
  }] },
}] } };

const result = aggregateCompletedWeeks(payload, 'TEST.CN', Date.UTC(2026, 0, 1) / 1000);
assert.equal(result.candles.length, 39, 'every chart must return exactly 39 weekly candles');
assert.equal(result.candles[0].open, 7, 'oldest excess candles must be removed');
assert.equal(result.candles.at(-1).open, 45, 'latest completed candle must remain visible');
assert.equal(result.candleCount, 39);
console.log('stock-chart: exact 39-candle contract passed');
