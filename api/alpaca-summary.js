export const config = { runtime: 'edge' };

export default async function handler() {
  const headers = { 'Content-Type': 'application/json', 'Cache-Control': 's-maxage=300, stale-while-revalidate=3600' };
  try {
    const key = process.env.ALPACA_API_KEY || process.env.APCA_API_KEY_ID;
    const secret = process.env.ALPACA_SECRET_KEY || process.env.APCA_API_SECRET_KEY;
    const base = (process.env.ALPACA_BASE_URL || 'https://api.alpaca.markets').replace(/\/$/, '');
    if (!key || !secret) throw new Error('Alpaca credentials unavailable');
    const brokerHeaders = { 'APCA-API-KEY-ID': key, 'APCA-API-SECRET-KEY': secret };
    const [accountResponse, positionsResponse] = await Promise.all([
      fetch(`${base}/v2/account`, { cache: 'no-store', headers: brokerHeaders }),
      fetch(`${base}/v2/positions`, { cache: 'no-store', headers: brokerHeaders }),
    ]);
    if (!accountResponse.ok) throw new Error(`Alpaca account HTTP ${accountResponse.status}`);
    if (!positionsResponse.ok) throw new Error(`Alpaca positions HTTP ${positionsResponse.status}`);
    const [account, rawPositions] = await Promise.all([accountResponse.json(), positionsResponse.json()]);
    const equity = Number(account.equity);
    if (!Number.isFinite(equity)) throw new Error('Invalid Alpaca equity');
    const inceptionRoi = (equity / 500 - 1) * 100;
    const investedValue = rawPositions.reduce((sum, position) => sum + Math.abs(Number(position.market_value) || 0), 0);
    const positions = rawPositions
      .map((position) => {
        const marketValue = Math.abs(Number(position.market_value) || 0);
        return {
          symbol: String(position.symbol || ''),
          marketValue,
          pctPnl: (Number(position.unrealized_plpc) || 0) * 100,
          portfolioWeight: investedValue > 0 ? marketValue / investedValue * 100 : 0,
        };
      })
      .filter((position) => position.symbol && position.marketValue > 0)
      .sort((a, b) => b.marketValue - a.marketValue);
    return new Response(JSON.stringify({ ok: true, equity, inceptionRoi, positions, investedValue, fetchedAt: new Date().toISOString() }), { status: 200, headers });
  } catch (error) {
    return new Response(JSON.stringify({ ok: false, error: String(error.message || error) }), { status: 502, headers });
  }
}
