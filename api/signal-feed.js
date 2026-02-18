// api/signal-feed.js — Vercel Serverless Function
// Fetches recent tweets from specified X accounts via Twitter's syndication API
// No API key required — uses the public embed timeline endpoint

const ACCOUNTS = [
  'BambroughKevin', 'zerohedge', 'KobeissiLetter', 'hkuppy', 'quakes99',
  'WatcherGuru', 'nntaleb', 'tferriss', 'TheEconomist', 'JohnPolomny',
  'SantiagoAuFund', 'BarbarianCap', 'JoshYoung', 'wmiddelkoop',
  'White_Rabbit_OG', 'colonelhomsi', 'HydroGraphInc'
];

const BASE_HEADERS = {
  'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
  'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
  'Accept-Language': 'en-US,en;q=0.9',
  'Accept-Encoding': 'gzip, deflate, br',
  'DNT': '1',
  'Connection': 'keep-alive',
};

const sleep = (ms) => new Promise(r => setTimeout(r, ms));

async function fetchUserTimeline(username, retries = 2) {
  for (let attempt = 0; attempt <= retries; attempt++) {
    try {
      if (attempt > 0) await sleep(1000 * attempt);

      const url = `https://syndication.twitter.com/srv/timeline-profile/screen-name/${username}?lang=en`;
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 8000);

      const resp = await fetch(url, {
        headers: { ...BASE_HEADERS, 'Referer': `https://twitter.com/${username}` },
        signal: controller.signal,
      });
      clearTimeout(timeout);

      if (resp.status === 429) {
        console.warn(`@${username}: rate limited (attempt ${attempt+1})`);
        if (attempt < retries) { await sleep(2000); continue; }
        return [];
      }
      if (!resp.ok) {
        console.warn(`@${username}: HTTP ${resp.status}`);
        return [];
      }

      const html = await resp.text();

      // Extract __NEXT_DATA__ JSON embedded in the page
      const match = html.match(/<script id="__NEXT_DATA__" type="application\/json">([\s\S]*?)<\/script>/);
      if (!match) {
        console.warn(`@${username}: no __NEXT_DATA__ found`);
        return [];
      }

      const data = JSON.parse(match[1]);
      const entries = data?.props?.pageProps?.timeline?.entries || [];

      const tweets = entries
        .filter(e => e.type === 'tweet' && e.content?.tweet)
        .slice(0, 20)
        .map(e => {
          const t = e.content.tweet;
          const user = t.user || {};
          const createdAt = t.created_at ? new Date(t.created_at) : new Date(0);
          const textRaw = t.full_text || t.text || '';
          // Strip t.co URLs from text for cleaner display
          const text = textRaw.replace(/https?:\/\/t\.co\/\S+/g, '').trim();

          return {
            id: t.id_str,
            text,
            author: user.name || username,
            handle: (user.screen_name || username).toLowerCase(),
            createdAt: createdAt.toISOString(),
            createdAtMs: createdAt.getTime(),
            likes: t.favorite_count || 0,
            retweets: t.retweet_count || 0,
            url: `https://x.com/${user.screen_name || username}/status/${t.id_str}`,
            avatar: user.profile_image_url_https || null,
          };
        })
        .filter(t => t.id && t.text.length > 0);

      return tweets;
    } catch (err) {
      if (err.name === 'AbortError') {
        console.warn(`@${username}: timeout on attempt ${attempt+1}`);
      } else {
        console.warn(`@${username}: ${err.message}`);
      }
      if (attempt < retries) await sleep(500);
    }
  }
  return [];
}

export default async function handler(req, res) {
  // CORS headers
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET');
  // Cache for 15 minutes on Vercel edge, serve stale for up to 30 min
  res.setHeader('Cache-Control', 's-maxage=900, stale-while-revalidate=1800');

  if (req.method !== 'GET') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  try {
    const results = {};
    const errors = [];

    // Process in batches of 4 with delay between batches
    const BATCH_SIZE = 4;
    for (let i = 0; i < ACCOUNTS.length; i += BATCH_SIZE) {
      const batch = ACCOUNTS.slice(i, i + BATCH_SIZE);
      const batchResults = await Promise.all(
        batch.map(async (acc) => {
          const tweets = await fetchUserTimeline(acc);
          return { acc, tweets };
        })
      );
      batchResults.forEach(({ acc, tweets }) => {
        results[acc] = tweets;
        if (!tweets.length) errors.push(acc);
      });
      // Brief pause between batches to avoid rate limiting
      if (i + BATCH_SIZE < ACCOUNTS.length) {
        await sleep(200);
      }
    }

    // Flatten and deduplicate by tweet ID
    const allTweets = Object.values(results).flat();
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

    const successCount = ACCOUNTS.length - errors.length;

    return res.status(200).json({
      ok: true,
      count: feed.length,
      fetchedAt: new Date().toISOString(),
      accountsFetched: successCount,
      accountsTotal: ACCOUNTS.length,
      posts: feed,
    });
  } catch (err) {
    console.error('Signal feed error:', err);
    return res.status(500).json({ ok: false, error: err.message, posts: [] });
  }
}
