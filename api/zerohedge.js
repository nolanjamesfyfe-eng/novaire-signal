// Live ZeroHedge RSS pool for the homepage refresh control.
export const config = { runtime: 'edge' };

const RSS_URL = 'https://feeds.feedburner.com/zerohedge/feed';

export function decodeXml(value) {
  let text = String(value || '').replace(/<!\[CDATA\[([\s\S]*?)\]\]>/g, '$1');
  const entities = {amp:'&',quot:'"',apos:"'",lt:'<',gt:'>',nbsp:' ',ensp:' ',emsp:' ',thinsp:' ',ndash:'–',mdash:'—',lsquo:'‘',rsquo:'’',ldquo:'“',rdquo:'”',hellip:'…'};
  for (let i = 0; i < 8; i++) {
    const next = text.replace(/&(#x[0-9a-f]+|#\d+|[a-z]+);/gi, (all, key) => {
      if (key[0] !== '#') return entities[key.toLowerCase()] ?? all;
      const n = key[1].toLowerCase() === 'x' ? parseInt(key.slice(2),16) : Number(key.slice(1));
      return n > 0 && n <= 0x10ffff ? String.fromCodePoint(n) : '';
    });
    if (next === text) break;
    text = next;
  }
  return text.trim();
}

function safeUrl(value, allowedHosts) {
  try {
    const url = new URL(String(value || '').trim());
    return url.protocol === 'https:' && allowedHosts.includes(url.hostname) ? url.href : '';
  } catch (_) {
    return '';
  }
}

export function textFromHtml(value) {
  return decodeXml(value).replace(/<(script|style)\b[^>]*>[\s\S]*?<\/\1>/gi, ' ').replace(/<[^>]+>/g, ' ').replace(/\u200b/g, '').replace(/\s+/g, ' ').trim();
}

function substantive(text) {
  return text.split(/\s+/).length >= 5 && /[a-z]/i.test(text) && !/^(authored|submitted) by\b|^(chart|source|image|photo|click to enlarge|advertisement|subscribe)\b/i.test(text);
}

export function firstSourcedSentence(description) {
  const decoded = decodeXml(description);
  const matches = [...decoded.matchAll(/<p[^>]*>([\s\S]*?)<\/p>/gi)];
  const paragraphs = (matches.length ? matches.map(m => m[1]) : [decoded]).map(textFromHtml).filter(substantive);
  const text = paragraphs[0] || '';
  const match = text.match(/^([\s\S]*?[.!?])(?:\s|$)/);
  return (match ? match[1] : text).slice(0, 320);
}

export function publicIntro(page) {
  const tags = [...String(page).matchAll(/<meta\b[^>]*>/gi)].map(m => m[0]);
  for (const name of ['og:description', 'description', 'twitter:description']) {
    for (const tag of tags) {
      const attrs = Object.fromEntries([...tag.matchAll(/([\w:-]+)\s*=\s*(["'])([\s\S]*?)\2/g)].map(m => [m[1].toLowerCase(), m[3]]));
      if ((attrs.property || attrs.name) === name) {
        const intro = firstSourcedSentence(attrs.content);
        if (intro) return intro;
      }
    }
  }
  const article = String(page).match(/<article\b[^>]*>([\s\S]*?)<\/article>/i);
  return article ? firstSourcedSentence(article[1]) : '';
}

function imageFromDescription(description) {
  const match = String(description || '').match(/<img[^>]+src=["']([^"']+)["'][^>]*>/i);
  return safeUrl(decodeXml(match ? match[1] : ''), ['assets.zerohedge.com', 'cms.zerohedge.com']);
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
    const selected = articles.slice(0, 12);
    await Promise.all(selected.map(async item => {
      item.excerptSource = 'publisher_rss';
      if (item.excerpt) return;
      try {
        const page = await fetch(item.url, {redirect: 'error', signal: AbortSignal.timeout(7000), headers: {'User-Agent': 'NovaireSignal/1.0'}});
        if (page.ok) item.excerpt = publicIntro((await page.text()).slice(0, 1500000));
        item.excerptSource = 'public_article_metadata_or_article';
      } catch (_) { /* Public metadata unavailable; no bypass or invented copy. */ }
    }));
    const usable = selected.filter(item => item.excerpt);
    return new Response(JSON.stringify({
      ok: usable.length > 0,
      fetchedAt: new Date().toISOString(),
      status: usable.length === selected.length ? 'ok' : 'partial',
      omittedWithoutIntro: selected.length - usable.length,
      articles: usable,
    }), { status: 200, headers });
  } catch (error) {
    return new Response(JSON.stringify({ ok: false, error: error.message, articles: [] }), { status: 502, headers });
  }
}
