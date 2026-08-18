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

// Yahoo overnight-nulls some completed small-cap daily bars (HG.CN on Aug 17
// printed C$6.84 but the 1d row arrived as 0/0/0/null). The weekly last close
// must still show that official completed print, never the prior Friday.
const weekStart = Date.UTC(2026, 7, 10, 13, 30) / 1000;
const overnightNulledPayload = { chart: { result: [{
  meta: {
    currency: 'CAD',
    exchangeTimezoneName: 'America/Toronto',
    regularMarketPrice: 6.84,
    regularMarketTime: Date.UTC(2026, 7, 17, 19, 59, 59) / 1000,
    currentTradingPeriod: { regular: { end: Date.UTC(2026, 7, 18, 20) / 1000 } },
  },
  timestamp: [...timestamps.slice(-38), weekStart, weekStart + 86400, weekStart + 2 * 86400, weekStart + 3 * 86400, weekStart + 4 * 86400, weekStart + 7 * 86400],
  indicators: { quote: [{
    open: [...values.slice(-38), 6.95, 7.40, 6.80, 6.49, 6.12, 0],
    high: [...values.slice(-38).map(v => v + 1), 7.46, 7.40, 6.97, 6.60, 6.77, 0],
    low: [...values.slice(-38).map(v => v - 1), 6.80, 6.68, 6.26, 5.92, 5.92, 0],
    close: [...values.slice(-38).map(v => v + .5), 7.05, 6.73, 6.28, 5.92, 6.51, null],
    volume: [...values.slice(-38).map(v => v * 100), 100, 200, 300, 400, 500, 0],
  }] },
}] } };
const beforeOpen = aggregateCompletedWeeks(overnightNulledPayload, 'HG.CN', Date.UTC(2026, 7, 18, 8, 8) / 1000);
assert.equal(beforeOpen.candles.at(-1).close, 6.84, 'overnight-nulled completed daily bar must still print the official last close');
assert.equal(beforeOpen.candles.at(-2).close, 6.51, 'prior completed week must remain intact');
assert.equal(beforeOpen.candles.at(-2).open, 6.95, 'prior week open must not be rewritten by the reconstructed close');
assert.notEqual(beforeOpen.candles.at(-1).close, 6.51, 'Friday close must not masquerade as the last official close');

const liveTuesday = structuredClone(overnightNulledPayload);
liveTuesday.chart.result[0].meta.regularMarketPrice = 7.11;
liveTuesday.chart.result[0].meta.regularMarketTime = Date.UTC(2026, 7, 18, 14, 15) / 1000;
liveTuesday.chart.result[0].meta.previousClose = 6.84;
const duringSession = aggregateCompletedWeeks(liveTuesday, 'HG.CN', Date.UTC(2026, 7, 18, 14, 15) / 1000);
assert.equal(duringSession.candles.at(-1).close, 6.84, 'live session quote must not replace the last official close');

const missingMonday = structuredClone(overnightNulledPayload);
missingMonday.chart.result[0].timestamp.pop();
for (const key of ['open', 'high', 'low', 'close', 'volume']) missingMonday.chart.result[0].indicators.quote[0][key].pop();
const injected = aggregateCompletedWeeks(missingMonday, 'HG.CN', Date.UTC(2026, 7, 18, 8, 8) / 1000);
assert.equal(injected.candles.at(-1).close, 6.84, 'missing completed daily bar must still inject the official last close');
assert.equal(injected.candles.at(-2).close, 6.51, 'injected official close must open a new week rather than rewrite Friday');

const primary = structuredClone(payload), fallback = structuredClone(payload);
primary.chart.result[0].timestamp = [timestamps.at(-1)];
for (const key of ['open', 'high', 'low', 'close', 'volume']) primary.chart.result[0].indicators.quote[0][key] = [99];
const merged = mergeChartPayloads(primary, fallback);
assert.equal(merged.chart.result[0].timestamp.length, 45, 'fallback history fills older dates');
assert.equal(merged.chart.result[0].indicators.quote[0].close.at(-1), 99, 'primary listing overrides fallback on overlapping dates');
console.log('stock-chart: exact 39-candle contract passed');
