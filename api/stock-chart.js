const ALLOWED = /^[A-Z0-9.^=-]{1,16}$/;
// MOLY.TO has fewer than 39 completed trading weeks after its listing change.
// Its US OTC line is the same company and provides the full nine-month history.
const HISTORY_ALIASES = { 'MOLY.TO': 'GRLRF' };

function finite(value) {
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}

function fridayCloseUtcSeconds(timestamp) {
  const d = new Date(timestamp * 1000);
  const day = d.getUTCDay();
  const daysFromMonday = (day + 6) % 7;
  const monday = new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate() - daysFromMonday));
  return Date.UTC(monday.getUTCFullYear(), monday.getUTCMonth(), monday.getUTCDate() + 4, 21, 0, 0) / 1000;
}

function marketDateKey(timestamp, timeZone = 'UTC') {
  return new Intl.DateTimeFormat('en-CA', {
    timeZone,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).format(new Date(timestamp * 1000));
}

export function mergeChartPayloads(primaryPayload, fallbackPayload) {
  const primary = primaryPayload?.chart?.result?.[0];
  const fallback = fallbackPayload?.chart?.result?.[0];
  if (!primary) return fallbackPayload;
  if (!fallback) return primaryPayload;
  const rows = new Map();
  for (const result of [fallback, primary]) {
    const quote = result.indicators?.quote?.[0] || {};
    (result.timestamp || []).forEach((time, index) => rows.set(Number(time), {
      time: Number(time), open: quote.open?.[index], high: quote.high?.[index],
      low: quote.low?.[index], close: quote.close?.[index], volume: quote.volume?.[index],
    }));
  }
  const merged = [...rows.values()].sort((a, b) => a.time - b.time);
  return { chart: { result: [{
    ...primary,
    timestamp: merged.map(row => row.time),
    indicators: { ...primary.indicators, quote: [{
      open: merged.map(row => row.open), high: merged.map(row => row.high),
      low: merged.map(row => row.low), close: merged.map(row => row.close),
      volume: merged.map(row => row.volume),
    }] },
  }] } };
}

export function aggregateCompletedWeeks(payload, symbol, nowSeconds = Date.now() / 1000) {
  const result = payload?.chart?.result?.[0];
  const quote = result?.indicators?.quote?.[0];
  const timestamps = result?.timestamp || [];
  if (!quote || !timestamps.length) throw new Error('No chart data');
  const timeZone = result.meta?.exchangeTimezoneName || 'UTC';
  const today = marketDateKey(nowSeconds, timeZone);
  const regularSessionEnd = finite(result.meta?.currentTradingPeriod?.regular?.end);
  const currentSessionIsClosed = regularSessionEnd !== null && nowSeconds >= regularSessionEnd;
  const weeks = new Map();
  timestamps.forEach((time, index) => {
    // Include today's bar only after the exchange's regular session has ended.
    // This matters in Bangkok, where the latest official North American close
    // arrives early the next morning while it is still the same date in-market.
    const rowDate = marketDateKey(Number(time), timeZone);
    if (rowDate > today || (rowDate === today && !currentSessionIsClosed)) return;
    const row = {
      time: Number(time),
      open: finite(quote.open?.[index]),
      high: finite(quote.high?.[index]),
      low: finite(quote.low?.[index]),
      close: finite(quote.close?.[index]),
      volume: finite(quote.volume?.[index]) ?? 0,
    };
    if (![row.time, row.open, row.high, row.low, row.close].every(Number.isFinite)) return;
    // Thin OTC feeds sometimes publish a synthetic all-zero row when no trade
    // occurred. It is not a closing price and must not distort the candle.
    if ([row.open, row.high, row.low, row.close].some(value => value <= 0)) return;
    const weekEnd = fridayCloseUtcSeconds(row.time);
    const current = weeks.get(weekEnd);
    if (!current) {
      weeks.set(weekEnd, { ...row, time: weekEnd, volume: row.volume });
      return;
    }
    current.high = Math.max(current.high, row.high);
    current.low = Math.min(current.low, row.low);
    current.close = row.close;
    current.volume += row.volume;
  });
  const candles = [...weeks.values()]
    .sort((a, b) => a.time - b.time)
    .slice(-39);
  if (candles.length !== 39) throw new Error('Insufficient history for 39 weekly candles');
  const highest = candles.reduce((best, candle, index) => candle.high > best.price ? { price: candle.high, index, time: candle.time } : best, { price: -Infinity, index: 0, time: 0 });
  const lowest = candles.reduce((best, candle, index) => candle.low < best.price ? { price: candle.low, index, time: candle.time } : best, { price: Infinity, index: 0, time: 0 });
  return {
    symbol,
    currency: result.meta?.currency || '',
    interval: '1wk',
    range: '9mo',
    candleCount: 39,
    candleRule: 'Current weekly candle updated through prior market close',
    highest,
    lowest,
    candles,
  };
}

export default async function handler(req, res) {
  const symbol = String(req.query?.symbol || '').trim().toUpperCase();
  if (!ALLOWED.test(symbol)) return res.status(400).json({ error: 'Invalid symbol' });
  try {
    const fetchPayload = async sourceSymbol => {
      const url = `https://query1.finance.yahoo.com/v8/finance/chart/${encodeURIComponent(sourceSymbol)}?range=1y&interval=1d&events=div%2Csplits`;
      const response = await fetch(url, { headers: { 'User-Agent': 'Mozilla/5.0 NovaireSignal/1.0' } });
      if (!response.ok) throw new Error(`Market data HTTP ${response.status}`);
      return response.json();
    };
    const primaryPayload = await fetchPayload(symbol);
    const historyAlias = HISTORY_ALIASES[symbol];
    const payload = historyAlias
      ? mergeChartPayloads(primaryPayload, await fetchPayload(historyAlias))
      : primaryPayload;
    const data = aggregateCompletedWeeks(payload, symbol);
    if (historyAlias) data.historySource = historyAlias;
    res.setHeader('Cache-Control', 's-maxage=3600, stale-while-revalidate=86400');
    return res.status(200).json(data);
  } catch (error) {
    return res.status(502).json({ error: 'Chart temporarily unavailable' });
  }
}
