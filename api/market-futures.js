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

const INVESTING_NAMES = {
  'ES=F': {exchange:'S&P 500', derived:'US 500'},
  'NQ=F': {exchange:'Nasdaq 100', derived:'US Tech 100'},
  'YM=F': {exchange:'Dow Jones', derived:'US 30'},
};

function parseNumber(value) {
  const parsed = Number(String(value || '').replaceAll(',', '').replace('%', '').replace('−', '-').replace('+', '').trim());
  return Number.isFinite(parsed) ? parsed : null;
}

export function parseInvestingFutures(markdown) {
  const lines = String(markdown).split('\n').filter(line => line.trim().startsWith('|'));
  const result = {};
  for (const [symbol, names] of Object.entries(INVESTING_NAMES)) {
    result[symbol] = {};
    for (const [kind, name] of Object.entries(names)) {
      const row = lines.find(line => line.includes(`**${name}**`) && (kind !== 'derived' || line.includes('derived')) && (kind !== 'exchange' || !line.includes('derived')));
      if (!row) continue;
      const cells = row.trim().replace(/^\||\|$/g, '').split('|').map(cell => cell.trim());
      const price = parseNumber(cells[3]);
      const change = parseNumber(cells[7]);
      if (price === null || change === null) continue;
      result[symbol][kind] = {
        price,
        change,
        name: kind === 'exchange' ? 'Investing.com Exchange' : 'Investing.com Derived',
        period: kind === 'exchange' ? 'exchange futures session' : 'derived futures pulse',
      };
    }
  }
  return result;
}

function median(values) {
  const sorted = values.filter(Number.isFinite).toSorted((a, b) => a - b);
  if (!sorted.length) return null;
  const middle = Math.floor(sorted.length / 2);
  return sorted.length % 2 ? sorted[middle] : (sorted[middle - 1] + sorted[middle]) / 2;
}

export function buildConsensusQuote(yahoo, investing = {}) {
  const sources = [];
  if (Number.isFinite(Number(yahoo?.change))) sources.push({name:'Yahoo Finance', price:Number(yahoo.price), change:Number(yahoo.change), basis:'exchange settlement'});
  for (const kind of ['exchange', 'derived']) {
    const quote = investing?.[kind];
    if (Number.isFinite(Number(quote?.change))) sources.push({name:quote.name, price:Number(quote.price), change:Number(quote.change), basis:quote.period});
  }
  const change = median(sources.map(source => source.change));
  const signs = new Set(sources.map(source => Math.sign(source.change)).filter(Boolean));
  const signal = signs.size > 1 ? 'mixed' : (change > 0 ? 'bullish' : change < 0 ? 'bearish' : 'flat');
  return {
    ...yahoo,
    price: investing?.exchange?.price ?? yahoo?.price ?? investing?.derived?.price ?? null,
    change: change === null ? null : Math.round(change * 100) / 100,
    source: 'Consensus: Yahoo Finance + Investing.com',
    period: 'cross-source futures consensus',
    signal,
    sourceCount: sources.length,
    sources,
  };
}

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

  const investingPromise = process.env.FIRECRAWL_API_KEY
    ? fetch('https://api.firecrawl.dev/v2/scrape', {
        method: 'POST',
        headers: {'Authorization':`Bearer ${process.env.FIRECRAWL_API_KEY}`,'Content-Type':'application/json'},
        body: JSON.stringify({url:'https://www.investing.com/indices/indices-futures',formats:['markdown'],onlyMainContent:true}),
      }).then(async response => {
        if (!response.ok) throw new Error(`Investing.com Firecrawl HTTP ${response.status}`);
        const payload = await response.json();
        return parseInvestingFutures(payload?.data?.markdown || '');
      })
    : Promise.reject(new Error('FIRECRAWL_API_KEY unavailable'));

  const [futureSettled, indexSettled, investingSettled] = await Promise.all([
    Promise.allSettled(FUTURES.map(item => fetchQuote(item, 'futures session'))),
    Promise.allSettled(INDICES.map(item => fetchQuote(item, 'cash session'))),
    Promise.allSettled([investingPromise]),
  ]);
  const yahooBySymbol = Object.fromEntries(
    futureSettled.filter(item => item.status === 'fulfilled').map(item => [item.value.symbol, item.value]),
  );
  const investing = investingSettled[0]?.status === 'fulfilled' ? investingSettled[0].value : {};
  const quotes = FUTURES.flatMap(meta => {
    const yahoo = yahooBySymbol[meta.symbol] || {symbol:meta.symbol, label:meta.label, short:meta.short, price:null, change:null};
    const consensus = buildConsensusQuote(yahoo, investing[meta.symbol]);
    return consensus.sourceCount ? [{...consensus, ...meta}] : [];
  });
  const indices = indexSettled.filter(item => item.status === 'fulfilled').map(item => item.value);
  const errors = [...futureSettled, ...indexSettled, ...investingSettled]
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
