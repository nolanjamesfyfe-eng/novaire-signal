// Live ZeroHedge RSS pool for the homepage refresh control.
export const config = { runtime: 'edge' };

const RSS_URL = 'https://feeds.feedburner.com/zerohedge/feed';

function decodeXml(value) {
  return String(value || '')
    .replace(/<!\[CDATA\[([\s\S]*?)\]\]>/g, '$1')
    .replace(/&amp;/g, '&')
    .replace(/&quot;/g, '"')
    .replace(/&#39;|&apos;/g, "'")
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .trim();
}

function tag(xml, name) {
  const match = xml.match(new RegExp(`<${name}[^>]*>([\\s\\S]*?)<\\/${name}>`, 'i'));
  return decodeXml(match ? match[1] : '');
}

export default async function handler(req) {
  const headers = {
    'Content-Type': 'application/json; charset=utf-8',
    'Cache-Control': 'no-store, max-age=0',
  };
  if (req.method !== 'GET') {
    return new Response(JSON.stringify({ ok: false, error: 'Method not allowed' }), { status: 405, headers });
  }

  try {
    const response = await fetch(RSS_URL, {
      cache: 'no-store',
      headers: { 'User-Agent': 'Mozilla/5.0 (compatible; NovaireSignal/1.0)' },
    });
    if (!response.ok) throw new Error(`RSS HTTP ${response.status}`);
    const xml = await response.text();
    const items = [...xml.matchAll(/<item>([\s\S]*?)<\/item>/gi)];
    const seen = new Set();
    const articles = [];
    for (const [, item] of items) {
      const title = tag(item, 'title');
      const url = tag(item, 'link');
      const publishedAt = tag(item, 'pubDate');
      if (!title || !/^https?:\/\//.test(url) || seen.has(url)) continue;
      seen.add(url);
      articles.push({ title, url, publishedAt });
    }
    return new Response(JSON.stringify({
      ok: true,
      fetchedAt: new Date().toISOString(),
      articles: articles.slice(0, 12),
    }), { status: 200, headers });
  } catch (error) {
    return new Response(JSON.stringify({ ok: false, error: error.message, articles: [] }), { status: 502, headers });
  }
}
