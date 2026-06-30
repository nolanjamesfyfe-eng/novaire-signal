// api/signal-feed.js — Vercel Edge Function
// Fetches via Nitter RSS (reliable, no Twitter API rate-limits)

export const config = { runtime: 'edge' };

const NITTER_BASE = 'https://nitter.net';

const ACCOUNTS = [
  'BambroughKevin','zerohedge','KobeissiLetter','hkuppy','quakes99',
  'WatcherGuru','nntaleb','tferriss','JohnPolomny',
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

    // Top four by engagement, with recency as the tie-breaker when RSS lacks metrics.
    // Keep one post per handle so one noisy account does not eat the whole compact scanner.
    const now = Date.now();
    const fresh = unique.filter(t => (now - t.createdAtMs) <= 24 * 60 * 60 * 1000);
    fresh.sort((a, b) => ((b.likes + b.retweets) - (a.likes + a.retweets)) || (b.createdAtMs - a.createdAtMs));

    const seenHandles = new Set();
    const posts = [];
    for (const post of fresh) {
      if (seenHandles.has(post.handle)) continue;
      post.slot = 'engagement';
      post.slot_order = posts.length + 1;
      post.engagementScore = post.likes + post.retweets;
      posts.push(post);
      seenHandles.add(post.handle);
      if (posts.length >= 4) break;
    }

    const body = JSON.stringify({
      ok: true,
      count: posts.length,
      accountsWithPosts: new Set(posts.map(p => p.handle)).size,
      fetchedAt: new Date().toISOString(),
      windowHours: 24,
      curation: 'top4_engagement_no_economist',
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
