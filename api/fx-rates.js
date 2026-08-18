export const config = { runtime: 'edge' };

const CURRENCIES = ['CAD', 'THB', 'AUD', 'COP', 'EUR', 'RUB', 'KRW', 'JPY'];
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

export default async function handler() {
  const headers = {
    'Content-Type': 'application/json',
    'Cache-Control': 's-maxage=300, stale-while-revalidate=900'
  };

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
      rates[code] = currentRate;
      previousRates[code] = previousRate;
      changes[code] = ((currentRate / previousRate) - 1) * 100;
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
