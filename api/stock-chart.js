const ALLOWED = /^[A-Z0-9.^=-]{1,16}$/;

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

export function aggregateCompletedWeeks(payload, symbol, nowSeconds = Date.now() / 1000) {
  const result = payload?.chart?.result?.[0];
  const quote = result?.indicators?.quote?.[0];
  const timestamps = result?.timestamp || [];
  if (!quote || !timestamps.length) throw new Error('No chart data');
  const weeks = new Map();
  timestamps.forEach((time, index) => {
    const row = {
      time: Number(time),
      open: finite(quote.open?.[index]),
      high: finite(quote.high?.[index]),
      low: finite(quote.low?.[index]),
      close: finite(quote.close?.[index]),
      volume: finite(quote.volume?.[index]) ?? 0,
    };
    if (![row.time, row.open, row.high, row.low, row.close].every(Number.isFinite)) return;
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
    .filter(candle => candle.time <= nowSeconds)
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
    candleRule: 'Finalized after Friday market close',
    highest,
    lowest,
    candles,
  };
}

export default async function handler(req, res) {
  const symbol = String(req.query?.symbol || '').trim().toUpperCase();
  if (!ALLOWED.test(symbol)) return res.status(400).json({ error: 'Invalid symbol' });
  try {
    const url = `https://query1.finance.yahoo.com/v8/finance/chart/${encodeURIComponent(symbol)}?range=1y&interval=1d&events=div%2Csplits`;
    const response = await fetch(url, { headers: { 'User-Agent': 'Mozilla/5.0 NovaireSignal/1.0' } });
    if (!response.ok) throw new Error(`Market data HTTP ${response.status}`);
    const data = aggregateCompletedWeeks(await response.json(), symbol);
    res.setHeader('Cache-Control', 's-maxage=3600, stale-while-revalidate=86400');
    return res.status(200).json(data);
  } catch (error) {
    return res.status(502).json({ error: 'Chart temporarily unavailable' });
  }
}
