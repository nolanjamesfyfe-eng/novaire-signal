// Exact Investing.com commodities screen used as Novaire Signal's reference.
export const config = { runtime: 'edge' };

const USER_AGENT = 'Mozilla/5.0 (compatible; NovaireSignal/1.0; +https://novairesignal.com)';

async function scrapePage(url) {
  const key = process.env.FIRECRAWL_API_KEY;
  if (key) {
    const response = await fetch('https://api.firecrawl.dev/v2/scrape', {
      method: 'POST',
      headers: {'Authorization':`Bearer ${key}`,'Content-Type':'application/json'},
      body: JSON.stringify({url, formats:['markdown'], onlyMainContent:true}),
    });
    if (response.ok) {
      const payload = await response.json();
      const markdown = payload?.data?.markdown || '';
      if (markdown.trim()) return markdown;
    }
  }
  const live = await fetch(url, {headers:{'User-Agent': USER_AGENT, 'Accept':'text/html'}});
  if (!live.ok) throw new Error(`direct scrape HTTP ${live.status}`);
  return await live.text();
}

const INSTRUMENTS = [
  ['GOLD', 'Gold'], ['SILVER', 'Silver'], ['COPPER', 'Copper'],
  ['WTI', 'Crude Oil'],
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

async function fetchYahooCoreCommodities() {
  const symbols = {GOLD:'GC=F', SILVER:'SI=F', COPPER:'HG=F', WTI:'CL=F'};
  return Promise.all(Object.entries(symbols).map(async ([symbol, ticker]) => {
    const result = (await fetchYahooChart(ticker))?.chart?.result?.[0];
    const timestamps = result?.timestamp || [];
    const closes = result?.indicators?.quote?.[0]?.close || [];
    const bars = timestamps.map((timestamp, index) => ({timestamp:Number(timestamp), close:Number(closes[index])}))
      .filter(bar => Number.isFinite(bar.timestamp) && Number.isFinite(bar.close) && bar.close > 0);
    if (bars.length < 2) throw new Error(`${ticker}: fewer than two sessions`);
    const previous = bars.at(-2).close, price = bars.at(-1).close;
    return {symbol, name:INSTRUMENTS.find(item => item[0] === symbol)?.[1], price, previous,
      change:(price - previous) / previous * 100, source:'Yahoo Finance fallback', period:'futures session',
      quoteTime:new Date(bars.at(-1).timestamp * 1000).toISOString()};
  }));
}

export default async function handler(req) {
  const headers = {'Content-Type':'application/json','Cache-Control':'s-maxage=30, stale-while-revalidate=60'};
  try {
    const quotes = parseInvestingCommodities(await scrapePage('https://www.investing.com/commodities/real-time-futures'));
    if (quotes.length !== INSTRUMENTS.length) throw new Error(`Only ${quotes.length}/${INSTRUMENTS.length} quotes parsed`);
    quotes.push(parseDiesel(await fetchYahooChart('HO=F')));
    const uranium = parseUranium(await scrapePage('https://tradingeconomics.com/commodity/uranium'));
    if (!uranium) throw new Error('Uranium quote not parsed');
    quotes.push(uranium);
    return new Response(JSON.stringify({ok:true, source:'Investing.com + Trading Economics', fetchedAt:new Date().toISOString(), quotes}), {status:200, headers});
  } catch (error) {
    try {
      const quotes = await fetchYahooCoreCommodities();
      quotes.push(parseDiesel(await fetchYahooChart('HO=F')));
      const uraniumResponse = await fetch('https://tradingeconomics.com/commodity/uranium', {headers:{'User-Agent':'Mozilla/5.0'}});
      if (!uraniumResponse.ok) throw new Error(`Uranium HTTP ${uraniumResponse.status}`);
      const uranium = parseUranium(await uraniumResponse.text());
      if (!uranium) throw new Error('Uranium quote not parsed');
      quotes.push(uranium);
      return new Response(JSON.stringify({ok:true, degraded:true, source:'Yahoo Finance fallback + Trading Economics', fetchedAt:new Date().toISOString(), quotes}), {status:206, headers});
    } catch (fallbackError) {
      return new Response(JSON.stringify({ok:false, source:'Investing.com', quotes:[], error:`${error.message}; fallback: ${fallbackError.message}`}), {status:502, headers});
    }
  }
}