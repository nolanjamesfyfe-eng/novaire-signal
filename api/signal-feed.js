// api/signal-feed.js — Vercel Edge Function
// Fetches via Nitter RSS (reliable, no Twitter API rate-limits)

export const config = { runtime: 'edge' };

const NITTER_BASE = 'https://nitter.net';

const ACCOUNTS = [
  'BambroughKevin','zerohedge','KobeissiLetter','hkuppy','quakes99',
  'WatcherGuru','nntaleb','tferriss','TheEconomist','JohnPolomny',
  'SantiagoAuFund','BarbarianCap','JoshYoung','wmiddelkoop',
  'White_Rabbit_OG','colonelhomsi','HydroGraphInc'
];

async function fetchUserTimeline(username) {
  try {
    const url = `${NITTER_BASE}/${username}/rss`;
    const resp = await fetch(url, {
      headers: { 'User-Agent': 'Mozilla/5.0 (compatible; NovaireSig/1.0)' },
    });
    if (!resp.ok) return { username, tweets: [], error: `HTTP ${resp.status}` };

    const xml = await resp.text();
    // Parse RSS items
    const items = [...xml.matchAll(/<item>([\s\S]*?)<\/item>/g)];
    const tweets = [];

    for (const [, itemXml] of items.slice(0, 20)) {
      const titleMatch = itemXml.match(/<title><!\[CDATA\[([\s\S]*?)\]\]><\/title>/) ||
                         itemXml.match(/<title>([\s\S]*?)<\/title>/);
      const linkMatch  = itemXml.match(/<link>([\s\S]*?)<\/link>/);
      const pubMatch   = itemXml.match(/<pubDate>([\s\S]*?)<\/pubDate>/);

      let text = titleMatch ? titleMatch[1].trim() : '';
      // Strip RT/reply prefixes
      text = text.replace(/^R to @\S+:\s*/, '').replace(/^RT by @\S+:\s*/, '').trim();
      if (!text || text.length < 5) continue;

      let link = linkMatch ? linkMatch[1].trim() : '';
      link = link.replace(/https?:\/\/nitter\.[^\/]+\//, 'https://x.com/');

      let createdAtMs = 0;
      let createdAt = new Date().toISOString();
      if (pubMatch) {
        const d = new Date(pubMatch[1].trim());
        if (!isNaN(d)) { createdAtMs = d.getTime(); createdAt = d.toISOString(); }
      }

      const idMatch = link.match(/\/status\/(\d+)/);
      tweets.push({
        id:          idMatch ? idMatch[1] : String(createdAtMs),
        text,
        author:      username,
        handle:      username,
        createdAt,
        createdAtMs,
        likes:       0,
        retweets:    0,
        url:         link || `https://x.com/${username}`,
        avatar:      null,
      });
    }
    return { username, tweets };
  } catch (err) {
    return { username, tweets: [], error: err.message };
  }
}

export default async function handler(req) {
  const corsHeaders = {
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Methods': 'GET',
    'Cache-Control': 's-maxage=900, stale-while-revalidate=1800',
    'Content-Type': 'application/json',
  };

  if (req.method === 'OPTIONS') {
    return new Response(null, { status: 200, headers: corsHeaders });
  }
  if (req.method !== 'GET') {
    return new Response(JSON.stringify({ error: 'Method not allowed' }), { status: 405, headers: corsHeaders });
  }

  try {
    // Fetch all accounts in parallel on edge network
    const results = await Promise.all(ACCOUNTS.map(fetchUserTimeline));
    const allTweets = results.flatMap(r => r.tweets);
    const errors = results.filter(r => r.error).map(r => ({ username: r.username, error: r.error }));

    // Deduplicate by ID
    const seen = new Set();
    const unique = allTweets.filter(t => {
      if (seen.has(t.id)) return false;
      seen.add(t.id);
      return true;
    });

    // Hard cutoff: guaranteed accounts (ZeroHedge, Kobeissi, Economist) = 4h max
    // All others = 24h max
    const GUARANTEED = new Set(['zerohedge', 'KobeissiLetter', 'TheEconomist']);
    const now = Date.now();
    const fresh = unique.filter(t => {
      const maxAge = GUARANTEED.has(t.handle) ? 4 * 60 * 60 * 1000 : 24 * 60 * 60 * 1000;
      return (now - t.createdAtMs) <= maxAge;
    });

    // Sort newest first
    fresh.sort((a, b) => b.createdAtMs - a.createdAtMs);

    const posts = fresh.slice(0, 60);

    const body = JSON.stringify({
      ok: true,
      count: posts.length,
      accountsWithPosts: new Set(posts.map(p => p.handle)).size,
      fetchedAt: new Date().toISOString(),
      errors,
      posts,
    });

    return new Response(body, { status: 200, headers: corsHeaders });
  } catch (err) {
    return new Response(
      JSON.stringify({ ok: false, error: err.message, posts: [] }),
      { status: 500, headers: corsHeaders }
    );
  }
}
