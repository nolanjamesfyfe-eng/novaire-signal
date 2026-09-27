'use strict';

const { clearSessionCookie, requestOriginAllowed, safeEqual, sessionCookie } = require('../lib/health-session');

// Best-effort per-instance limiter. Serverless instances do not share this map;
// production-grade global enforcement requires an external atomic store/WAF rule.
const attempts = new Map();
const WINDOW_MS = 15 * 60 * 1000;
const MAX_ATTEMPTS = 5;
const MAX_BODY_BYTES = 1024;

function respond(res, status, body, extra = {}) {
  res.statusCode = status;
  res.setHeader('Content-Type', 'application/json; charset=utf-8');
  res.setHeader('Cache-Control', 'no-store, max-age=0');
  res.setHeader('X-Robots-Tag', 'noindex, nofollow, noarchive');
  for (const [name, value] of Object.entries(extra)) res.setHeader(name, value);
  res.end(JSON.stringify(body));
}

function clientKey(req) {
  return String(req.headers['x-forwarded-for'] || req.socket?.remoteAddress || 'unknown').split(',')[0].trim().slice(0, 80);
}

async function readJson(req) {
  let body = '';
  for await (const chunk of req) {
    body += chunk;
    if (Buffer.byteLength(body) > MAX_BODY_BYTES) throw Object.assign(new Error('too large'), { status: 413 });
  }
  try { return JSON.parse(body || '{}'); }
  catch { throw Object.assign(new Error('invalid json'), { status: 400 }); }
}

module.exports = async function handler(req, res) {
  if (req.method !== 'POST' && req.method !== 'DELETE') {
    return respond(res, 405, { error: 'Method not allowed' }, { Allow: 'POST, DELETE' });
  }
  if (!requestOriginAllowed(req)) return respond(res, 403, { error: 'Forbidden' });

  if (req.method === 'DELETE') {
    return respond(res, 200, { ok: true }, { 'Set-Cookie': clearSessionCookie() });
  }

  const secret = process.env.NOS_AUTH_SECRET || '';
  const expected = process.env.NOS_ACCESS_PIN || '';
  if (!secret || !expected) return respond(res, 503, { error: 'Health record access is not configured.' });

  const key = clientKey(req);
  const now = Date.now();
  const entry = attempts.get(key) || { failures: 0, resetAt: now + WINDOW_MS, blockedUntil: 0 };
  if (entry.resetAt <= now) Object.assign(entry, { failures: 0, resetAt: now + WINDOW_MS, blockedUntil: 0 });
  if (entry.blockedUntil > now) {
    return respond(res, 429, { error: 'Too many attempts.' }, { 'Retry-After': String(Math.ceil((entry.blockedUntil - now) / 1000)) });
  }

  let data;
  try { data = await readJson(req); }
  catch (error) { return respond(res, error.status || 400, { error: error.status === 413 ? 'Request too large' : 'Invalid request' }); }
  const supplied = typeof data.pin === 'string' ? data.pin : '';
  if (!/^\d{5}$/.test(supplied) || !/^\d{5}$/.test(expected) || !safeEqual(supplied, expected)) {
    entry.failures += 1;
    if (entry.failures >= MAX_ATTEMPTS) entry.blockedUntil = now + WINDOW_MS;
    attempts.set(key, entry);
    return respond(res, entry.blockedUntil ? 429 : 401, { error: entry.blockedUntil ? 'Too many attempts.' : 'Incorrect PIN.' }, entry.blockedUntil ? { 'Retry-After': '900' } : {});
  }

  attempts.delete(key);
  return respond(res, 200, { ok: true }, { 'Set-Cookie': sessionCookie(secret) });
};
