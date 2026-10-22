'use strict';

const healthSession = require('../lib/health-session');
const studySession = require('../lib/study-session');
const streak = require('../lib/study-streak');
const store = require('../lib/study-streak-store');

const MAX_BODY_BYTES = 96 * 1024;
const MAX_MERGE_DATES = 4096;

function respond(res, status, body, extra = {}) {
  res.statusCode = status;
  res.setHeader('Content-Type', 'application/json; charset=utf-8');
  res.setHeader('Cache-Control', 'private, no-store, max-age=0');
  res.setHeader('Pragma', 'no-cache');
  res.setHeader('X-Robots-Tag', 'noindex, nofollow, noarchive');
  for (const [name, value] of Object.entries(extra)) res.setHeader(name, value);
  res.end(JSON.stringify(body));
}
async function readJson(req) {
  let body = '';
  for await (const chunk of req) {
    body += chunk;
    if (Buffer.byteLength(body) > MAX_BODY_BYTES) throw Object.assign(new Error('Request too large.'), { status: 413 });
  }
  try { return JSON.parse(body || '{}'); }
  catch { throw Object.assign(new Error('Invalid request.'), { status: 400 }); }
}
function canonicalIsoDate(value) {
  if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
  try { return new Date(`${value}T00:00:00Z`).toISOString().slice(0, 10) === value; }
  catch { return false; }
}
function sanitizeLocalDates(value, today) {
  if (value === undefined) return [];
  if (!Array.isArray(value) || value.length > MAX_MERGE_DATES || value.some(date => !canonicalIsoDate(date))) {
    throw Object.assign(new Error('Invalid local click dates.'), { status: 400 });
  }
  return [...new Set(value.filter(date => date >= streak.FEATURE_START_DATE && date <= today))].sort();
}
function payload(document, today, extra = {}) {
  return { ...streak.summarize(document, today), clickDates: document.clickDates, revision: document.revision, storage: 'private-cross-device', ...extra };
}

module.exports = async function handler(req, res) {
  if (!['GET', 'POST'].includes(req.method)) return respond(res, 405, { error: 'Method not allowed' }, { Allow: 'GET, POST' });
  if (!healthSession.requestOriginAllowed(req)) return respond(res, 403, { error: 'Same-origin request required.' });
  const secret = process.env.NOS_AUTH_SECRET || '';
  const studyAuthorized = studySession.verifySession(req.headers.cookie, secret);
  const healthAuthorized = healthSession.verifySession(req.headers.cookie, secret);
  if (!studyAuthorized && !healthAuthorized) return respond(res, 401, { error: 'Private study sync is not connected.' });
  if (!store.config()) return respond(res, 503, { error: 'Private cross-device streak storage is not configured.' });
  const headers = healthAuthorized && !studyAuthorized ? { 'Set-Cookie': studySession.sessionCookie(secret) } : {};
  try {
    const today = streak.bangkokDate(new Date());
    if (req.method === 'GET') return respond(res, 200, payload(await store.read(), today), headers);
    const data = await readJson(req);
    const action = data.action || 'click';
    if (!['click', 'merge'].includes(action)) return respond(res, 400, { error: 'Invalid study action.' }, headers);
    const localDates = sanitizeLocalDates(data.localDates, today);
    const dates = action === 'click' ? [...new Set([...localDates, today])] : localDates;
    const result = await store.mergeClickDates(dates);
    return respond(res, 200, payload(result.document, today, { deduplicated: result.deduplicated }), headers);
  } catch (error) {
    if (error?.status) return respond(res, error.status, { error: error.message }, headers);
    if (error?.code === 'CONFLICT') return respond(res, 409, { error: 'The streak changed on another device. Retry.' }, headers);
    return respond(res, 503, { error: 'Private click streak storage is temporarily unavailable.' }, headers);
  }
};
