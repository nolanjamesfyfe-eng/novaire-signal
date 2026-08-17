export const config = { runtime: 'edge' };

export default async function handler() {
  const headers = { 'Content-Type': 'application/json', 'Cache-Control': 's-maxage=300, stale-while-revalidate=3600' };
  try {
    const key = process.env.ALPACA_API_KEY || process.env.APCA_API_KEY_ID;
    const secret = process.env.ALPACA_SECRET_KEY || process.env.APCA_API_SECRET_KEY;
    const base = (process.env.ALPACA_BASE_URL || 'https://api.alpaca.markets').replace(/\/$/, '');
    if (!key || !secret) throw new Error('Alpaca credentials unavailable');
    const response = await fetch(`${base}/v2/account`, {
      cache: 'no-store',
      headers: { 'APCA-API-KEY-ID': key, 'APCA-API-SECRET-KEY': secret },
    });
    if (!response.ok) throw new Error(`Alpaca HTTP ${response.status}`);
    const account = await response.json();
    const equity = Number(account.equity);
    if (!Number.isFinite(equity)) throw new Error('Invalid Alpaca equity');
    const inceptionRoi = (equity / 500 - 1) * 100;
    return new Response(JSON.stringify({ ok: true, equity, inceptionRoi, fetchedAt: new Date().toISOString() }), { status: 200, headers });
  } catch (error) {
    return new Response(JSON.stringify({ ok: false, error: String(error.message || error) }), { status: 502, headers });
  }
}
