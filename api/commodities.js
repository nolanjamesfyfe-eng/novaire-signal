// Exact Investing.com commodities screen used as Novaire Signal's reference.
export const config = { runtime: 'edge' };

const INSTRUMENTS = [
  ['GOLD', 'Gold'], ['SILVER', 'Silver'], ['COPPER', 'Copper'],
  ['WTI', 'Crude Oil WTI'],
];

function parseUranium(markdown) {
  const match = String(markdown).match(/Uranium[^".]{0,160}?\bat\s+(\d+(?:\.\d+)?)\s*USD\/Lbs/i);
  return match ? {symbol:'URANIUM_SPOT', name:'Uranium', price:Number(match[1]), change:null, source:'Trading Economics', period:'spot benchmark'} : null;
}

export function parseInvestingCommodities(markdown) {
  const lines = String(markdown).split('\n');
  return INSTRUMENTS.flatMap(([symbol, name]) => {
    const slug = {GOLD:'gold',SILVER:'silver',COPPER:'copper',WTI:'crude-oil'}[symbol];
    const row = lines.find(line => line.includes(`](https://www.investing.com/commodities/${slug} "`));
    if (!row) return [];
    const cells = row.trim().replace(/^\||\|$/g, '').split('|').map(cell => cell.trim());
    const price = Number(cells[3]?.replaceAll(',', ''));
    const change = Number(cells[7]?.replace('%', '').replace('−', '-'));
    return Number.isFinite(price) && Number.isFinite(change)
      ? [{ symbol, name, price, change, source: 'Investing.com', period: 'daily' }]
      : [];
  });
}

export function parseDiesel(payload) {
  const result = payload?.chart?.result?.[0];
  const timestamps = result?.timestamp || [];
  const closes = result?.indicators?.quote?.[0]?.close || [];
  const bars = timestamps.map((timestamp, index) => ({timestamp:Number(timestamp), close:Number(closes[index])}))
    .filter(bar => Number.isFinite(bar.timestamp) && Number.isFinite(bar.close) && bar.close > 0);
  if (bars.length < 2) throw new Error('Fewer than two diesel futures sessions');
  const previous = bars.at(-2).close * 42;
  const price = bars.at(-1).close * 42;
  return {symbol:'DIESEL', name:'Diesel', price, previous,
    change:(price - previous) / previous * 100,
    source:'Yahoo Finance (NYMEX ULSD)', period:'futures session',
    quoteTime:new Date(bars.at(-1).timestamp * 1000).toISOString()};
}

async function fetchYahooChart(symbol) {
  const response = await fetch(`https://query1.finance.yahoo.com/v8/finance/chart/${encodeURIComponent(symbol)}?range=5d&interval=1d`,
    {headers:{'User-Agent':'NovaireSignal/1.0'}});
  if (!response.ok) throw new Error(`${symbol}: Yahoo HTTP ${response.status}`);
  return response.json();
}

export default async function handler(req) {
  const headers = {'Content-Type':'application/json','Cache-Control':'s-maxage=30, stale-while-revalidate=60'};
  try {
    if (!process.env.FIRECRAWL_API_KEY) throw new Error('FIRECRAWL_API_KEY unavailable');
    const response = await fetch('https://api.firecrawl.dev/v2/scrape', {
      method: 'POST',
      headers: {'Authorization':`Bearer ${process.env.FIRECRAWL_API_KEY}`,'Content-Type':'application/json'},
      body: JSON.stringify({url:'https://www.investing.com/commodities/real-time-futures',formats:['markdown'],onlyMainContent:true}),
    });
    if (!response.ok) throw new Error(`Firecrawl HTTP ${response.status}`);
    const payload = await response.json();
    const quotes = parseInvestingCommodities(payload?.data?.markdown || '');
    if (quotes.length !== INSTRUMENTS.length) throw new Error(`Only ${quotes.length}/${INSTRUMENTS.length} quotes parsed`);
    quotes.push(parseDiesel(await fetchYahooChart('HO=F')));
    const uraniumResponse = await fetch('https://api.firecrawl.dev/v2/scrape', {
      method: 'POST',
      headers: {'Authorization':`Bearer ${process.env.FIRECRAWL_API_KEY}`,'Content-Type':'application/json'},
      body: JSON.stringify({url:'https://tradingeconomics.com/commodity/uranium',formats:['markdown'],onlyMainContent:true}),
    });
    if (!uraniumResponse.ok) throw new Error(`Uranium Firecrawl HTTP ${uraniumResponse.status}`);
    const uraniumPayload = await uraniumResponse.json();
    const uranium = parseUranium(uraniumPayload?.data?.markdown || '');
    if (!uranium) throw new Error('Uranium quote not parsed');
    quotes.push(uranium);
    return new Response(JSON.stringify({ok:true, source:'Investing.com + Trading Economics', fetchedAt:new Date().toISOString(), quotes}), {status:200, headers});
  } catch (error) {
    return new Response(JSON.stringify({ok:false, source:'Investing.com', quotes:[], error:error.message}), {status:502, headers});
  }
}