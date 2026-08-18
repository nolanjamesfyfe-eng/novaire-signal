import assert from 'node:assert/strict';
import { aggregateCompletedWeeks, mergeChartPayloads } from '../api/stock-chart.js';

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

const monday = Date.UTC(2026, 7, 17, 13, 30) / 1000;
const tuesday = monday + 86400;
const wednesday = tuesday + 86400;
const partialWeekPayload = { chart: { result: [{
  meta: { currency: 'CAD', exchangeTimezoneName: 'America/Toronto' },
  timestamp: [...timestamps.slice(-38), monday, tuesday, wednesday],
  indicators: { quote: [{
    open: [...values.slice(-38), 10, 11, 99],
    high: [...values.slice(-38).map(v => v + 1), 12, 14, 100],
    low: [...values.slice(-38).map(v => v - 1), 9, 10, 98],
    close: [...values.slice(-38).map(v => v + .5), 11, 13, 99],
    volume: [...values.slice(-38).map(v => v * 100), 1000, 2000, 9999],
  }] },
}] } };
const intraweek = aggregateCompletedWeeks(partialWeekPayload, 'TEST.CN', Date.UTC(2026, 7, 19, 16) / 1000);
assert.equal(intraweek.candles.length, 39, 'current partial week must replace the oldest completed week');
assert.equal(intraweek.candles.at(-1).open, 10, 'current weekly candle starts at Monday open');
assert.equal(intraweek.candles.at(-1).close, 13, 'current weekly candle closes at prior market day');
assert.equal(intraweek.candles.at(-1).high, 14, 'today\'s unfinished bar must be excluded');
assert.equal(intraweek.candles.at(-1).volume, 3000, 'partial weekly volume aggregates completed days');
assert.equal(intraweek.candleRule, 'Current weekly candle updated through prior market close');

partialWeekPayload.chart.result[0].meta.currentTradingPeriod = { regular: { end: Date.UTC(2026, 7, 19, 20) / 1000 } };
const afterClose = aggregateCompletedWeeks(partialWeekPayload, 'TEST.CN', Date.UTC(2026, 7, 19, 22) / 1000);
assert.equal(afterClose.candles.at(-1).close, 99, 'today\'s daily bar becomes official after regular market close');
assert.equal(afterClose.candles.at(-1).volume, 12999, 'after-close weekly volume includes the completed session');

const zeroRowPayload = structuredClone(payload);
zeroRowPayload.chart.result[0].timestamp.push(timestamps.at(-1) + 86400);
for (const key of ['open', 'high', 'low', 'close', 'volume']) zeroRowPayload.chart.result[0].indicators.quote[0][key].push(0);
const withoutSyntheticZero = aggregateCompletedWeeks(zeroRowPayload, 'OTC', Date.UTC(2026, 0, 2) / 1000);
assert.equal(withoutSyntheticZero.candles.at(-1).close, 45.5, 'synthetic zero-price OTC rows must be ignored');

const primary = structuredClone(payload), fallback = structuredClone(payload);
primary.chart.result[0].timestamp = [timestamps.at(-1)];
for (const key of ['open', 'high', 'low', 'close', 'volume']) primary.chart.result[0].indicators.quote[0][key] = [99];
const merged = mergeChartPayloads(primary, fallback);
assert.equal(merged.chart.result[0].timestamp.length, 45, 'fallback history fills older dates');
assert.equal(merged.chart.result[0].indicators.quote[0].close.at(-1), 99, 'primary listing overrides fallback on overlapping dates');
console.log('stock-chart: exact 39-candle contract passed');
