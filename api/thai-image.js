// Thumbnail relay for the Thailand Expat Brief. Publishers block browser
// hotlinking, so fetch server-side from an allowlist of Thai news image hosts only.
export const config = { runtime: 'edge' };

const HOSTS = new Set([
  'thethaiger.com', 'www.thethaiger.com',
  'thaiexaminer.com', 'www.thaiexaminer.com',
  'bangkokpost.com', 'www.bangkokpost.com', 'static.bangkokpost.com',
]);
const MAX_BYTES = 3 * 1024 * 1024;

export default async function handler(request) {
  let target;
  try {
    target = new URL(new URL(request.url).searchParams.get('u') || '');
  } catch (_) {
    return new Response('Bad image URL', { status: 400 });
  }
  if (target.protocol !== 'https:' || !HOSTS.has(target.hostname)) {
    return new Response('Host not allowed', { status: 403 });
  }
  try {
    const upstream = await fetch(target.href, {
      headers: { 'User-Agent': 'Mozilla/5.0 (compatible; NovaireSignal/1.0)', Accept: 'image/*' },
      redirect: 'follow',
    });
    const type = upstream.headers.get('content-type') || '';
    const finalHost = new URL(upstream.url || target.href).hostname;
    if (!upstream.ok || !type.startsWith('image/') || !HOSTS.has(finalHost)) {
      return new Response('Image unavailable', { status: 502 });
    }
    const body = await upstream.arrayBuffer();
    if (body.byteLength > MAX_BYTES) return new Response('Image too large', { status: 413 });
    return new Response(body, {
      headers: {
        'Content-Type': type,
        'Cache-Control': 'public, max-age=86400, s-maxage=604800, immutable',
        'X-Content-Type-Options': 'nosniff',
      },
    });
  } catch (_) {
    return new Response('Image unavailable', { status: 502 });
  }
}
