// api/signal-feed.js — Vercel Edge Function
// Uses Edge Runtime (Cloudflare's network) to avoid IP rate-limiting on Twitter's syndication API

export const config = { runtime: 'edge' };

const ACCOUNTS = [
  'BambroughKevin','zerohedge','KobeissiLetter','hkuppy','quakes99',
  'WatcherGuru','nntaleb','tferriss','TheEconomist','JohnPolomny',
  'SantiagoAuFund','BarbarianCap','JoshYoung','wmiddelkoop',
  'White_Rabbit_OG','colonelhomsi','HydroGraphInc'
];

async function fetchUserTimeline(username) {
  try {
    const url = `https://syndication.twitter.com/srv/timeline-profile/screen-name/${username}?lang=en`;
    const resp = await fetch(url, {
      headers: {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
      },
      // Edge runtime's fetch has built-in 30s timeout
    });

    if (!resp.ok) return { username, tweets: [], error: `HTTP ${resp.status}` };

    const html = await resp.text();
    const match = html.match(/<script id="__NEXT_DATA__" type="application\/json">([\s\S]*?)<\/script>/);
    if (!match) return { username, tweets: [], error: 'no_data' };

    const data = JSON.parse(match[1]);
    const entries = data?.props?.pageProps?.timeline?.entries || [];

    const tweets = entries
      .filter(e => e.type === 'tweet' && e.content?.tweet?.id_str)
      .slice(0, 15)
      .map(e => {
        const t = e.content.tweet;
        const u = t.user || {};
        const createdAt = new Date(t.created_at || 0);
        return {
          id: t.id_str,
          text: (t.full_text || t.text || '').replace(/https?:\/\/t\.co\/\S+/g, '').trim(),
          author: u.name || username,
          handle: u.screen_name || username,
          createdAt: createdAt.toISOString(),
          createdAtMs: createdAt.getTime(),
          likes: t.favorite_count || 0,
          retweets: t.retweet_count || 0,
          url: `https://x.com/${u.screen_name || username}/status/${t.id_str}`,
          avatar: u.profile_image_url_https || null,
        };
      })
      .filter(t => t.text.length > 0);

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

    // Sort newest first
    unique.sort((a, b) => b.createdAtMs - a.createdAtMs);

    const posts = unique.slice(0, 60);

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
