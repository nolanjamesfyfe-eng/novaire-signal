// api/signal-feed.js — Vercel Serverless Function
// Fetches recent tweets from specified X accounts via Twitter's syndication API
// No API key required — uses the public embed timeline endpoint

const ACCOUNTS = [
  'BambroughKevin', 'zerohedge', 'KobeissiLetter', 'hkuppy', 'quakes99',
  'WatcherGuru', 'nntaleb', 'tferriss', 'TheEconomist', 'JohnPolomny',
  'SantiagoAuFund', 'BarbarianCap', 'JoshYoung', 'wmiddelkoop',
  'White_Rabbit_OG', 'colonelhomsi', 'HydroGraphInc'
];

const HEADERS = {
  'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
  'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
  'Accept-Language': 'en-US,en;q=0.9',
  'Cache-Control': 'no-cache',
};

async function fetchUserTimeline(username) {
  try {
    const url = `https://syndication.twitter.com/srv/timeline-profile/screen-name/${username}?lang=en`;
    const resp = await fetch(url, { headers: HEADERS, signal: AbortSignal.timeout(8000) });
    if (!resp.ok) return [];
    const html = await resp.text();

    // Extract __NEXT_DATA__ JSON embedded in the page
    const match = html.match(/<script id="__NEXT_DATA__" type="application\/json">([\s\S]*?)<\/script>/);
    if (!match) return [];

    const data = JSON.parse(match[1]);
    const entries = data?.props?.pageProps?.timeline?.entries || [];

    return entries
      .filter(e => e.type === 'tweet' && e.content?.tweet)
      .slice(0, 20) // take up to 20 per account, sort by recency globally
      .map(e => {
        const t = e.content.tweet;
        const user = t.user || {};
        const createdAt = t.created_at ? new Date(t.created_at) : new Date(0);
        // Skip if tweet is older than 7 days
        return {
          id: t.id_str,
          text: (t.full_text || t.text || '').replace(/https?:\/\/t\.co\/\S+/g, '').trim(),
          author: user.name || username,
          handle: user.screen_name || username,
          createdAt: createdAt.toISOString(),
          createdAtMs: createdAt.getTime(),
          likes: t.favorite_count || 0,
          retweets: t.retweet_count || 0,
          url: `https://x.com/${user.screen_name || username}/status/${t.id_str}`,
          avatar: user.profile_image_url_https || null,
        };
      })
      .filter(Boolean);
  } catch (err) {
    console.error(`Failed to fetch @${username}:`, err.message);
    return [];
  }
}

export default async function handler(req, res) {
  // CORS headers
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET');
  // Cache for 15 minutes
  res.setHeader('Cache-Control', 's-maxage=900, stale-while-revalidate=1800');

  if (req.method !== 'GET') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  try {
    // Fetch all accounts in parallel (with concurrency limit)
    const BATCH_SIZE = 6;
    let allTweets = [];

    for (let i = 0; i < ACCOUNTS.length; i += BATCH_SIZE) {
      const batch = ACCOUNTS.slice(i, i + BATCH_SIZE);
      const results = await Promise.all(batch.map(fetchUserTimeline));
      allTweets = allTweets.concat(results.flat());
    }

    // Deduplicate by tweet ID
    const seen = new Set();
    const unique = allTweets.filter(t => {
      if (seen.has(t.id)) return false;
      seen.add(t.id);
      return true;
    });

    // Sort by recency (newest first)
    unique.sort((a, b) => b.createdAtMs - a.createdAtMs);

    // Return top 60
    const feed = unique.slice(0, 60);

    return res.status(200).json({
      ok: true,
      count: feed.length,
      fetchedAt: new Date().toISOString(),
      posts: feed,
    });
  } catch (err) {
    console.error('Signal feed error:', err);
    return res.status(500).json({ ok: false, error: err.message });
  }
}
