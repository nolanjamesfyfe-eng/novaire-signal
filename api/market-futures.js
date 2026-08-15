// Live index-futures snapshot for the Novaire Signal market pulse.
export const config = { runtime: 'edge' };

const FUTURES = [
  { symbol: 'ES=F', label: 'S&P 500', short: 'S&P FUT' },
  { symbol: 'NQ=F', label: 'Nasdaq 100', short: 'NASDAQ FUT' },
  { symbol: 'YM=F', label: 'Dow Jones', short: 'DOW FUT' },
];

const INDICES = [
  { symbol: '^GSPC', label: 'S&P 500', short: 'S&P CASH' },
  { symbol: '^IXIC', label: 'Nasdaq Composite', short: 'NASDAQ CASH' },
  { symbol: '^DJI', label: 'Dow Jones', short: 'DOW CASH' },
];

export function parseYahooChart(payload, period = 'futures session') {
  const result = payload?.chart?.result?.[0];
  const timestamps = result?.timestamp || [];
  const closes = result?.indicators?.quote?.[0]?.close || [];
  const valid = timestamps
    .map((timestamp, index) => [Number(timestamp), Number(closes[index])])
    .filter(([, close]) => Number.isFinite(close) && close > 0);

  if (valid.length < 2) throw new Error('Yahoo returned fewer than two valid bars');

  const previous = valid.at(-2)[1];
  const price = valid.at(-1)[1];
  const quoteTimestamp = Number(result?.meta?.regularMarketTime || valid.at(-1)[0]);
  return {
    price,
    previous,
    change: Math.round((((price - previous) / previous) * 100) * 100) / 100,
    source: 'Yahoo Finance',
    period,
    quoteTime: new Date(quoteTimestamp * 1000).toISOString(),
  };
}

async function fetchQuote(meta, period) {
  const url = `https://query1.finance.yahoo.com/v8/finance/chart/${encodeURIComponent(meta.symbol)}?range=5d&interval=1d`;
  const response = await fetch(url, {
    headers: { 'User-Agent': 'NovaireSignal/1.0' },
  });
  if (!response.ok) throw new Error(`${meta.symbol}: HTTP ${response.status}`);
  return { ...meta, ...parseYahooChart(await response.json(), period) };
}

export default async function handler(req) {
  const headers = {
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Methods': 'GET',
    'Cache-Control': 's-maxage=30, stale-while-revalidate=60',
    'Content-Type': 'application/json',
  };

  if (req.method === 'OPTIONS') return new Response(null, { status: 200, headers });
  if (req.method !== 'GET') {
    return new Response(JSON.stringify({ ok: false, error: 'Method not allowed' }), { status: 405, headers });
  }

  const [futureSettled, indexSettled] = await Promise.all([
    Promise.allSettled(FUTURES.map(item => fetchQuote(item, 'futures session'))),
    Promise.allSettled(INDICES.map(item => fetchQuote(item, 'cash session'))),
  ]);
  const quotes = futureSettled.filter(item => item.status === 'fulfilled').map(item => item.value);
  const indices = indexSettled.filter(item => item.status === 'fulfilled').map(item => item.value);
  const errors = [...futureSettled, ...indexSettled]
    .filter(item => item.status === 'rejected')
    .map(item => item.reason.message);
  const loaded = quotes.length + indices.length;
  const status = loaded === FUTURES.length + INDICES.length ? 200 : loaded ? 206 : 502;

  return new Response(JSON.stringify({
    ok: loaded === FUTURES.length + INDICES.length,
    fetchedAt: new Date().toISOString(),
    quotes,
    indices,
    errors,
  }), { status, headers });
}
