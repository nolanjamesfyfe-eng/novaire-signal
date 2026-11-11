// Live commodity tiles for Novaire Signal.
//
// Reliability contract (2026-11-11 outage: Investing.com 403'd the edge,
// Firecrawl ran out of credits, and a Trading Economics wording change from
// "at" to "fell to" made the all-or-nothing handler 502, freezing every tile):
//   * Structured Yahoo futures bars are the primary source. No HTML scraping
//     on the hot path for exchange-traded contracts.
//   * Every symbol is fetched independently. One bad provider can only blank
//     its own tile, never the whole strip.
//   * Uranium (no liquid Yahoo contract) parses Trading Economics' dated
//     metadata sentence by number + unit + date, verb-agnostic.
export const config = { runtime: 'edge' };

const UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36';

// Yahoo 429s spoofed browser UAs from datacenter IPs; a plain bot UA is served.
const YAHOO_UA = 'NovaireSignal/1.0';

export const YAHOO_COMMODITIES = {
  GOLD:   {ticker: 'GC=F', name: 'Gold'},
  SILVER: {ticker: 'SI=F', name: 'Silver'},
  COPPER: {ticker: 'HG=F', name: 'Copper'},
  WTI:    {ticker: 'CL=F', name: 'Crude Oil'},
  DIESEL: {ticker: 'HO=F', name: 'Diesel', multiplier: 42},  // USD/gal -> USD/bbl
};
export const EXPECTED_SYMBOLS = [...Object.keys(YAHOO_COMMODITIES), 'URANIUM_SPOT'];

async function timedFetch(url, init = {}, ms = 6000) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), ms);
  try { return await fetch(url, {...init, signal: controller.signal}); }
  finally { clearTimeout(timer); }
}

export function parseYahooFuture(payload, symbol, meta) {
  const result = payload?.chart?.result?.[0];
  const timestamps = result?.timestamp || [];
  const closes = result?.indicators?.quote?.[0]?.close || [];
  const bars = timestamps.map((t, i) => ({t: Number(t), c: closes[i] == null ? NaN : Number(closes[i])}))
    .filter(b => Number.isFinite(b.t) && Number.isFinite(b.c) && b.c > 0);
  if (bars.length < 2) throw new Error(`${meta.ticker}: fewer than two sessions`);
  const m = meta.multiplier || 1;
  const previous = bars.at(-2).c * m;
  // Prefer the live meta print so the tile moves intraday.
  const live = Number(result?.meta?.regularMarketPrice);
  const price = (Number.isFinite(live) && live > 0 ? live : bars.at(-1).c) * m;
  const t = Number(result?.meta?.regularMarketTime) || bars.at(-1).t;
  return {symbol, name: meta.name, price, previous,
    change: (price - previous) / previous * 100,
    source: meta.multiplier ? 'Yahoo Finance (NYMEX ULSD)' : 'Yahoo Finance (front-month futures)',
    period: 'futures session', quoteTime: new Date(t * 1000).toISOString()};
}

// "Uranium fell to 90.95 USD/Lbs on November 10, 2026, down 0.49% from the previous day."
// Verb-agnostic, and anchored on "USD/Lbs on <Month D, YYYY>" so forecast copy
// ("expected to trade at 92.50 USD/LBS by the end of this quarter") never matches.
export function parseUranium(html) {
  const text = String(html).replace(/&#39;/g, "'");
  const m = text.match(/Uranium\s+[a-z ]{2,40}?\b(?:to|at)\s+(\d+(?:\.\d+)?)\s*USD\/Lbs\s+on\s+([A-Z][a-z]+ \d{1,2}, \d{4})(?:,\s*(up|down)\s+(\d+(?:\.\d+)?)%)?/);
  if (!m) return null;
  const price = Number(m[1]);
  if (!(price > 10 && price < 1000)) return null;
  const change = m[3] ? (m[3] === 'down' ? -1 : 1) * Number(m[4]) : null;
  const asOf = new Date(`${m[2]} 00:00:00 UTC`);
  return {symbol: 'URANIUM_SPOT', name: 'Uranium', price, change,
    source: 'Trading Economics', period: 'U3O8 benchmark, daily',
    quoteTime: Number.isNaN(asOf.getTime()) ? null : asOf.toISOString()};
}

async function fetchYahoo(symbol) {
  const meta = YAHOO_COMMODITIES[symbol];
  let lastError;
  for (const host of ['query1', 'query2']) {
    try {
      const r = await timedFetch(`https://${host}.finance.yahoo.com/v8/finance/chart/${encodeURIComponent(meta.ticker)}?range=5d&interval=1d`,
        {headers: {'User-Agent': YAHOO_UA}});
      if (!r.ok) throw new Error(`${meta.ticker}: Yahoo HTTP ${r.status}`);
      return parseYahooFuture(await r.json(), symbol, meta);
    } catch (e) { lastError = e; }
  }
  throw lastError;
}

async function fetchUranium(origin) {
  try {
    const r = await timedFetch('https://tradingeconomics.com/commodity/uranium', {headers: {'User-Agent': UA, 'Accept': 'text/html'}});
    if (!r.ok) throw new Error(`Uranium HTTP ${r.status}`);
    const q = parseUranium(await r.text());
    if (!q) throw new Error('Uranium quote not parsed');
    return q;
  } catch (liveError) {
    // Uranium is a once-a-day benchmark; the refresh job publishes the print.
    const r = await timedFetch(`${origin}/uranium_cache.json?_=${Date.now()}`, {cache: 'no-store'});
    if (!r.ok) throw new Error(`${liveError.message}; snapshot HTTP ${r.status}`);
    const q = await r.json();
    if (!(Number(q?.price) > 10)) throw new Error(`${liveError.message}; snapshot invalid`);
    return q;
  }
}

export default async function handler(req) {
  const headers = {'Content-Type': 'application/json', 'Cache-Control': 's-maxage=30, stale-while-revalidate=60'};
  const origin = req?.url ? new URL(req.url).origin : 'https://novairesignal.com';
  const settled = await Promise.allSettled(EXPECTED_SYMBOLS.map(s => s === 'URANIUM_SPOT' ? fetchUranium(origin) : fetchYahoo(s)));
  const quotes = [], errors = [];
  settled.forEach((r, i) => r.status === 'fulfilled' ? quotes.push(r.value)
    : errors.push(`${EXPECTED_SYMBOLS[i]}: ${r.reason?.message || r.reason}`));
  const ok = quotes.length > 0;
  return new Response(JSON.stringify({ok, complete: errors.length === 0, source: 'Yahoo Finance + Trading Economics',
    fetchedAt: new Date().toISOString(), quotes, errors}), {status: ok ? 200 : 502, headers});
}
