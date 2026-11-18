// Generic Yahoo quote + symbol lookup for user-customised Wizard Signal boxes.
// GET /api/quotes?s=^N225,CL=F        -> { ok, quotes:[{symbol,name,price,change,currency}] }
// GET /api/quotes?q=nikkei&kind=index -> { ok, match:{symbol,name,price,change,currency} }
export const config = { runtime: 'edge' };

const UA = { 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36' };
const SYMBOL_RE = /^[A-Za-z0-9^=.\-]{1,20}$/;

export function parseChart(payload) {
  const result = payload?.chart?.result?.[0];
  if (!result) return null;
  const meta = result.meta || {};
  const closes = (result.indicators?.quote?.[0]?.close || []).map(Number).filter(v => Number.isFinite(v) && v > 0);
  const price = Number.isFinite(Number(meta.regularMarketPrice)) ? Number(meta.regularMarketPrice) : closes.at(-1);
  const prev = closes.length >= 2 ? closes.at(-2) : Number(meta.chartPreviousClose);
  if (!Number.isFinite(price)) return null;
  const change = Number.isFinite(prev) && prev > 0 ? Math.round(((price - prev) / prev) * 10000) / 100 : null;
  return { symbol: meta.symbol, name: meta.shortName || meta.longName || meta.symbol, price, change, currency: meta.currency || null };
}

async function quote(symbol) {
  const r = await fetch(`https://query1.finance.yahoo.com/v8/finance/chart/${encodeURIComponent(symbol)}?range=5d&interval=1d`, { headers: UA });
  if (!r.ok) throw new Error(`${symbol}: HTTP ${r.status}`);
  const q = parseChart(await r.json());
  if (!q) throw new Error(`${symbol}: no data`);
  return q;
}

const KIND_TYPES = {
  index: ['INDEX', 'FUTURE', 'ETF', 'EQUITY'],
  commodity: ['FUTURE', 'ETF'],
  currency: ['CURRENCY'],
};

async function search(q, kind) {
  const r = await fetch(`https://query2.finance.yahoo.com/v1/finance/search?q=${encodeURIComponent(q)}&quotesCount=8&newsCount=0&listsCount=0`, { headers: UA });
  if (!r.ok) throw new Error(`search HTTP ${r.status}`);
  const rows = (await r.json())?.quotes || [];
  const types = KIND_TYPES[kind] || KIND_TYPES.index;
  for (const t of types) {
    const hit = rows.find(row => row.quoteType === t && row.symbol);
    if (hit) return { symbol: hit.symbol, name: hit.shortname || hit.longname || hit.symbol };
  }
  return null;
}

export default async function handler(req) {
  const headers = { 'Content-Type': 'application/json', 'Cache-Control': 's-maxage=30, stale-while-revalidate=60' };
  const url = new URL(req.url);
  try {
    const q = (url.searchParams.get('q') || '').trim().slice(0, 60);
    if (q) {
      const kind = url.searchParams.get('kind') || 'index';
      let found = null;
      if (SYMBOL_RE.test(q) && /[=^.]/.test(q)) found = { symbol: q.toUpperCase() };
      if (!found) found = await search(q, kind);
      if (!found) return new Response(JSON.stringify({ ok: false, error: 'No match' }), { status: 404, headers });
      const live = await quote(found.symbol);
      return new Response(JSON.stringify({ ok: true, match: { ...live, name: found.name || live.name } }), { status: 200, headers });
    }
    const symbols = (url.searchParams.get('s') || '').split(',').map(s => s.trim()).filter(s => SYMBOL_RE.test(s)).slice(0, 16);
    if (!symbols.length) return new Response(JSON.stringify({ ok: false, error: 'No symbols' }), { status: 400, headers });
    const settled = await Promise.allSettled(symbols.map(quote));
    const quotes = settled.map((s, i) => s.status === 'fulfilled' ? { ...s.value, symbol: symbols[i] } : { symbol: symbols[i], error: String(s.reason?.message || s.reason) });
    return new Response(JSON.stringify({ ok: true, quotes, fetchedAt: new Date().toISOString() }), { status: 200, headers });
  } catch (error) {
    return new Response(JSON.stringify({ ok: false, error: String(error.message || error) }), { status: 502, headers });
  }
}
