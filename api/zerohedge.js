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

function safeUrl(value, allowedHosts) {
  try {
    const url = new URL(String(value || '').trim());
    return url.protocol === 'https:' && allowedHosts.includes(url.hostname) ? url.href : '';
  } catch (_) {
    return '';
  }
}

function textFromHtml(value) {
  return decodeXml(String(value || '').replace(/<[^>]+>/g, ' ')).replace(/\s+/g, ' ').trim();
}

function firstSourcedSentence(description) {
  const paragraphs = [...String(description || '').matchAll(/<p[^>]*>([\s\S]*?)<\/p>/gi)]
    .map((match) => textFromHtml(match[1]))
    .filter((text) => text && !/^(authored|submitted) by\b/i.test(text));
  const text = paragraphs[0] || '';
  const match = text.match(/^([\s\S]*?[.!?])(?:\s|$)/);
  return (match ? match[1] : text).slice(0, 320);
}

function imageFromDescription(description) {
  const match = String(description || '').match(/<img[^>]+src=["']([^"']+)["'][^>]*>/i);
  return safeUrl(decodeXml(match ? match[1] : ''), ['assets.zerohedge.com']);
}

function imageAltFromDescription(description) {
  const image = String(description || '').match(/<img[^>]*>/i);
  const alt = image ? image[0].match(/\balt=["']([^"']*)["']/i) : null;
  return textFromHtml(alt ? alt[1] : '');
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
      const url = safeUrl(tag(item, 'link'), ['zerohedge.com', 'www.zerohedge.com']);
      const publishedAt = tag(item, 'pubDate');
      const description = tag(item, 'description');
      if (!title || !url || seen.has(url)) continue;
      seen.add(url);
      articles.push({
        title,
        url,
        publishedAt,
        excerpt: firstSourcedSentence(description),
        image: imageFromDescription(description),
        image_alt: imageAltFromDescription(description),
      });
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
