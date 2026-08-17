export const config = { runtime: 'edge' };

const CURRENCIES = ['CAD', 'THB', 'AUD', 'COP', 'EUR', 'RUB', 'KRW', 'JPY'];

export default async function handler() {
  const headers = { 'Content-Type': 'application/json', 'Cache-Control': 's-maxage=60, stale-while-revalidate=300' };
  try {
    const response = await fetch('https://open.er-api.com/v6/latest/USD', { cache: 'no-store' });
    if (!response.ok) throw new Error(`FX HTTP ${response.status}`);
    const data = await response.json();
    const rates = Object.fromEntries(CURRENCIES.flatMap(code =>
      Number.isFinite(Number(data.rates?.[code])) ? [[code, Number(data.rates[code])]] : []
    ));
    if (Object.keys(rates).length !== CURRENCIES.length) throw new Error('Incomplete FX response');
    return new Response(JSON.stringify({ ok: true, base: 'USD', rates, fetchedAt: new Date().toISOString() }), { status: 200, headers });
  } catch (error) {
    return new Response(JSON.stringify({ ok: false, error: String(error.message || error) }), { status: 502, headers });
  }
}
