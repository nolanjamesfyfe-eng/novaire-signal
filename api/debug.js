// Debug endpoint (Edge Runtime)
export const config = { runtime: 'edge' };

export default async function handler(req) {
  const { searchParams } = new URL(req.url);
  const username = searchParams.get('u') || 'WatcherGuru';
  const url = `https://syndication.twitter.com/srv/timeline-profile/screen-name/${username}?lang=en`;

  try {
    const resp = await fetch(url, {
      headers: {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml',
        'Accept-Language': 'en-US,en;q=0.9',
      },
    });

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

    return new Response(JSON.stringify({
      ok: resp.ok,
      status: resp.status,
      htmlLength: text.length,
      hasNextData,
      hasMatch: !!match,
      entryCount,
      firstTweet,
      htmlStart: text.substring(0, 200),
    }, null, 2), {
      headers: { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' }
    });
  } catch (err) {
    return new Response(JSON.stringify({ ok: false, error: err.message, errorType: err.name }, null, 2), {
      headers: { 'Content-Type': 'application/json' }
    });
  }
}
