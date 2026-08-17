const ALLOWED = /^[A-Z0-9.^=-]{1,16}$/;

function finite(value) {
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}

export function normalizeYahooChart(payload, symbol) {
  const result = payload?.chart?.result?.[0];
  const quote = result?.indicators?.quote?.[0];
  const timestamps = result?.timestamp || [];
  if (!quote || !timestamps.length) throw new Error('No chart data');
  const candles = timestamps.map((time, index) => ({
    time,
    open: finite(quote.open?.[index]),
    high: finite(quote.high?.[index]),
    low: finite(quote.low?.[index]),
    close: finite(quote.close?.[index]),
  })).filter(candle => [candle.open, candle.high, candle.low, candle.close].every(Number.isFinite));
  if (!candles.length) throw new Error('No complete candles');
  return {
    symbol,
    currency: result.meta?.currency || '',
    previousClose: finite(result.meta?.chartPreviousClose ?? result.meta?.previousClose),
    candles,
  };
}

export default async function handler(req, res) {
  const symbol = String(req.query?.symbol || '').trim().toUpperCase();
  if (!ALLOWED.test(symbol)) return res.status(400).json({ error: 'Invalid symbol' });
  try {
    const url = `https://query1.finance.yahoo.com/v8/finance/chart/${encodeURIComponent(symbol)}?range=9mo&interval=1wk&events=div%2Csplits`;
    const response = await fetch(url, { headers: { 'User-Agent': 'Mozilla/5.0 NovaireSignal/1.0' } });
    if (!response.ok) throw new Error(`Market data HTTP ${response.status}`);
    const data = normalizeYahooChart(await response.json(), symbol);
    res.setHeader('Cache-Control', 's-maxage=3600, stale-while-revalidate=86400');
    return res.status(200).json(data);
  } catch (error) {
    return res.status(502).json({ error: 'Chart temporarily unavailable' });
  }
}
