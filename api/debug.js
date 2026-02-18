// Debug endpoint - check if syndication API works from Vercel
export default async function handler(req, res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  
  const username = req.query.u || 'WatcherGuru';
  const url = `https://syndication.twitter.com/srv/timeline-profile/screen-name/${username}?lang=en`;
  
  try {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 8000);
    
    const resp = await fetch(url, {
      headers: {
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml',
      },
      signal: controller.signal,
    });
    clearTimeout(timer);
    
    const text = await resp.text();
    const hasNextData = text.includes('__NEXT_DATA__');
    const match = text.match(/<script id="__NEXT_DATA__" type="application\/json">([\s\S]*?)<\/script>/);
    
    let entryCount = 0;
    let firstTweet = null;
    if (match) {
      try {
        const data = JSON.parse(match[1]);
        const entries = data?.props?.pageProps?.timeline?.entries || [];
        entryCount = entries.length;
        const first = entries[0]?.content?.tweet;
        if (first) firstTweet = { id: first.id_str, created_at: first.created_at, text: (first.full_text||'').substring(0,80) };
      } catch(e) {
        firstTweet = { error: e.message };
      }
    }
    
    return res.status(200).json({
      ok: resp.ok,
      status: resp.status,
      htmlLength: text.length,
      hasNextData,
      hasMatch: !!match,
      entryCount,
      firstTweet,
      htmlStart: text.substring(0, 300),
    });
  } catch (err) {
    return res.status(200).json({
      ok: false,
      error: err.message,
      errorType: err.name,
    });
  }
}
