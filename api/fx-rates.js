export const config = { runtime: 'edge' };

const CURRENCIES = ['THB', 'CAD', 'AUD', 'COP', 'EUR', 'RUB', 'KRW', 'JPY'];
const PRIMARY_BASE = 'https://cdn.jsdelivr.net/npm/@fawazahmed0/currency-api';
const FALLBACK_BASE = 'https://latest.currency-api.pages.dev';

function previousTradingDate(isoDate) {
  const date = new Date(`${isoDate}T12:00:00Z`);
  const day = date.getUTCDay();
  date.setUTCDate(date.getUTCDate() - (day === 1 ? 3 : day === 0 ? 2 : day === 6 ? 1 : 1));
  return date.toISOString().slice(0, 10);
}

async function fetchSnapshot(version) {
  const suffix = `/v1/currencies/usd.min.json`;
  const urls = version === 'latest'
    ? [`${PRIMARY_BASE}@latest${suffix}`, `${FALLBACK_BASE}${suffix}`]
    : [`${PRIMARY_BASE}@${version}${suffix}`, `https://${version}.currency-api.pages.dev${suffix}`];

  let lastError;
  for (const url of urls) {
    try {
      const response = await fetch(url, { cache: 'no-store' });
      if (!response.ok) throw new Error(`FX source HTTP ${response.status}`);
      const data = await response.json();
      if (!data?.date || !data?.usd) throw new Error('Malformed FX snapshot');
      return { date: data.date, usd: data.usd, url };
    } catch (error) {
      lastError = error;
    }
  }
  throw lastError || new Error('FX source unavailable');
}

// Live layer (2026-11-11): the Fawaz snapshot publishes once a day, so tiles
// sat a full session behind (CAD 1.4118 vs market 1.4219). Yahoo FX bars are
// primary; each currency falls back to the daily snapshot independently.
const YAHOO_UA = 'NovaireSignal/1.0';

export function parseYahooFx(payload) {
  const result = payload?.chart?.result?.[0];
  const ts = result?.timestamp || [];
  const closes = result?.indicators?.quote?.[0]?.close || [];
  const bars = ts.map((t, i) => ({t: Number(t), c: closes[i] == null ? NaN : Number(closes[i])}))
    .filter(b => Number.isFinite(b.t) && Number.isFinite(b.c) && b.c > 0);
  if (bars.length < 2) throw new Error('fewer than two FX sessions');
  const live = Number(result?.meta?.regularMarketPrice);
  const rate = Number.isFinite(live) && live > 0 ? live : bars.at(-1).c;
  const previous = bars.at(-2).c;
  return {rate, previous, change: (rate / previous - 1) * 100,
    quoteTime: new Date((Number(result?.meta?.regularMarketTime) || bars.at(-1).t) * 1000).toISOString()};
}

async function fetchYahooFx(code) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 5000);
  try {
    const r = await fetch(`https://query1.finance.yahoo.com/v8/finance/chart/${code}%3DX?range=5d&interval=1d`,
      {headers: {'User-Agent': YAHOO_UA}, signal: controller.signal});
    if (!r.ok) throw new Error(`Yahoo HTTP ${r.status}`);
    return parseYahooFx(await r.json());
  } finally { clearTimeout(timer); }
}

export default async function handler(req) {
  const headers = {
    'Content-Type': 'application/json',
    'Cache-Control': 's-maxage=30, stale-while-revalidate=120'
  };
  // Customize drawer: ?c=GEL,MXN returns live Yahoo rates for just those codes.
  const asked = (() => { try { return (new URL(req.url).searchParams.get('c') || '').toUpperCase().split(',').filter(c => /^[A-Z]{3}$/.test(c) && c !== 'USD').slice(0, 12); } catch (_) { return []; } })();
  if (asked.length) {
    const got = await Promise.allSettled(asked.map(fetchYahooFx));
    const rates = {}, changes = {};
    asked.forEach((code, i) => { if (got[i].status === 'fulfilled') { rates[code] = got[i].value.rate; changes[code] = got[i].value.change; } });
    const missing = asked.filter(code => !(code in rates));
    if (missing.length) {
      try {
        const latest = await fetchSnapshot('latest');
        const prev = await fetchSnapshot(previousTradingDate(latest.date)).catch(() => null);
        for (const code of missing) {
          const r = Number(latest.usd[code.toLowerCase()]), p = Number(prev?.usd?.[code.toLowerCase()]);
          if (Number.isFinite(r) && r > 0) { rates[code] = r; if (Number.isFinite(p) && p > 0) changes[code] = (r / p - 1) * 100; }
        }
      } catch (_) {}
    }
    return new Response(JSON.stringify({ok: Object.keys(rates).length > 0, base: 'USD', rates, changes, source: 'Yahoo Finance FX', fetchedAt: new Date().toISOString()}), {status: 200, headers});
  }

  const live = await Promise.allSettled(CURRENCIES.map(fetchYahooFx));
  if (live.every(r => r.status === 'fulfilled')) {
    const rates = {}, previousRates = {}, changes = {}, quoteTimes = {};
    CURRENCIES.forEach((code, i) => {
      const q = live[i].value;
      rates[code] = q.rate; previousRates[code] = q.previous; changes[code] = q.change; quoteTimes[code] = q.quoteTime;
    });
    return new Response(JSON.stringify({ok: true, base: 'USD', rates, previousRates, changes, quoteTimes,
      changePeriod: 'vs prior FX session close', source: 'Yahoo Finance FX', fetchedAt: new Date().toISOString()}),
      {status: 200, headers});
  }

  try {
    const latest = await fetchSnapshot('latest');
    const comparisonDate = previousTradingDate(latest.date);
    const previous = await fetchSnapshot(comparisonDate);
    const rates = {};
    const previousRates = {};
    const changes = {};

    for (const code of CURRENCIES) {
      const key = code.toLowerCase();
      const currentRate = Number(latest.usd[key]);
      const previousRate = Number(previous.usd[key]);
      if (!Number.isFinite(currentRate) || currentRate <= 0 || !Number.isFinite(previousRate) || previousRate <= 0) {
        throw new Error(`Incomplete FX history for ${code}`);
      }
      const i = CURRENCIES.indexOf(code);
      const y = live[i].status === 'fulfilled' ? live[i].value : null;
      rates[code] = y ? y.rate : currentRate;
      previousRates[code] = y ? y.previous : previousRate;
      changes[code] = y ? y.change : ((currentRate / previousRate) - 1) * 100;
    }

    return new Response(JSON.stringify({
      ok: true,
      base: 'USD',
      rates,
      previousRates,
      changes,
      asOf: latest.date,
      comparisonDate: previous.date,
      changePeriod: 'previous FX trading day',
      source: 'Fawaz Ahmed Currency API',
      fetchedAt: new Date().toISOString()
    }), { status: 200, headers });
  } catch (error) {
    return new Response(JSON.stringify({ ok: false, error: String(error.message || error) }), { status: 502, headers });
  }
}
