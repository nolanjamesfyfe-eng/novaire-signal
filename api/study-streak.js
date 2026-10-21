'use strict';

const { requestOriginAllowed, verifySession } = require('../lib/health-session');
const streak = require('../lib/study-streak');
const store = require('../lib/study-streak-store');

function respond(res, status, body, extra = {}) {
  res.statusCode = status;
  res.setHeader('Content-Type', 'application/json; charset=utf-8');
  res.setHeader('Cache-Control', 'private, no-store, max-age=0');
  res.setHeader('Pragma', 'no-cache');
  res.setHeader('X-Robots-Tag', 'noindex, nofollow, noarchive');
  for (const [name, value] of Object.entries(extra)) res.setHeader(name, value);
  res.end(JSON.stringify(body));
}

module.exports = async function handler(req, res) {
  if (!['GET', 'POST'].includes(req.method)) return respond(res, 405, { error: 'Method not allowed' }, { Allow: 'GET, POST' });
  if (!requestOriginAllowed(req)) return respond(res, 403, { error: 'Same-origin request required.' });
  if (!verifySession(req.headers.cookie, process.env.NOS_AUTH_SECRET || '')) return respond(res, 401, { error: 'Private Signal session required.' });
  if (!store.config()) return respond(res, 503, { error: 'Private cross-device streak storage is not configured.' });
  try {
    const today = streak.bangkokDate(new Date());
    if (req.method === 'GET') {
      const document = await store.read();
      return respond(res, 200, { ...streak.summarize(document, today), revision: document.revision, storage: 'private-cross-device' });
    }
    const result = await store.recordClick(today);
    return respond(res, 200, { ...streak.summarize(result.document, today), revision: result.document.revision, deduplicated: result.deduplicated, storage: 'private-cross-device' });
  } catch (error) {
    if (error?.code === 'CONFLICT') return respond(res, 409, { error: 'The streak changed on another device. Retry the click.' });
    return respond(res, 503, { error: 'Private click streak storage is temporarily unavailable.' });
  }
};
