// api/signal-feed.js — Vercel Serverless Function
// Fetches tweets via Twitter syndication API (no API key needed)

const ACCOUNTS = [
  'BambroughKevin','zerohedge','KobeissiLetter','hkuppy','quakes99',
  'WatcherGuru','nntaleb','tferriss','TheEconomist','JohnPolomny',
  'SantiagoAuFund','BarbarianCap','JoshYoung','wmiddelkoop',
  'White_Rabbit_OG','colonelhomsi','HydroGraphInc'
];

async function fetchUserTimeline(username) {
  try {
    const url = `https://syndication.twitter.com/srv/timeline-profile/screen-name/${username}?lang=en`;
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 6000);

    const resp = await fetch(url, {
      headers: {
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml',
        'Accept-Language': 'en-US,en;q=0.9',
      },
      signal: controller.signal,
    });
    clearTimeout(timer);

    if (!resp.ok) return [];

    const html = await resp.text();
    const match = html.match(/<script id="__NEXT_DATA__" type="application\/json">([\s\S]*?)<\/script>/);
    if (!match) return [];

    const data = JSON.parse(match[1]);
    const entries = data?.props?.pageProps?.timeline?.entries || [];

    return entries
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
          handle: (u.screen_name || username),
          createdAt: createdAt.toISOString(),
          createdAtMs: createdAt.getTime(),
          likes: t.favorite_count || 0,
          retweets: t.retweet_count || 0,
          url: `https://x.com/${u.screen_name || username}/status/${t.id_str}`,
          avatar: u.profile_image_url_https || null,
        };
      })
      .filter(t => t.text.length > 0);
  } catch {
    return [];
  }
}

export default async function handler(req, res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Cache-Control', 's-maxage=900, stale-while-revalidate=1800');

  if (req.method === 'OPTIONS') return res.status(200).end();
  if (req.method !== 'GET') return res.status(405).json({ error: 'Method not allowed' });

  try {
    // Fetch all accounts in parallel
    const results = await Promise.all(ACCOUNTS.map(fetchUserTimeline));
    const allTweets = results.flat();

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
    const accountsWithPosts = new Set(posts.map(p => p.handle)).size;

    return res.status(200).json({
      ok: true,
      count: posts.length,
      accountsWithPosts,
      fetchedAt: new Date().toISOString(),
      posts,
    });
  } catch (err) {
    return res.status(500).json({ ok: false, error: err.message, posts: [] });
  }
}
