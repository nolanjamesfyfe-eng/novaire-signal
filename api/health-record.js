'use strict';

const { requestOriginAllowed, verifySession } = require('../lib/health-session');

const ALLOWED_FIELDS = ['region', 'label', 'summary', 'reportedFindings', 'carePlan', 'sourceDate', 'certainty'];
const PRIVATE_BODY_LIKENESS = Object.freeze({
  physique: 'Very lean runner build; tall, narrow silhouette with low bulk and prominent collarbones.',
  anatomicalLeftClavicle: 'Self-reported surgically repaired fracture with a large visible scar and slight bone prominence.',
  provenance: 'Self-reported by Novaire; no operative report or calibrated body scan reviewed.',
  modelingCertainty: 'Approximate visual likeness. Scar path and bone contour are interpretive, not verified clinical geometry.'
});
const MAX_ENV_BYTES = 16 * 1024;
const MAX_TEXT = 2000;
const MAX_LIST_ITEMS = 24;

function respond(res, status, body, extra = {}) {
  res.statusCode = status;
  res.setHeader('Content-Type', 'application/json; charset=utf-8');
  res.setHeader('Cache-Control', 'no-store, max-age=0');
  res.setHeader('Pragma', 'no-cache');
  res.setHeader('X-Robots-Tag', 'noindex, nofollow, noarchive');
  for (const [name, value] of Object.entries(extra)) res.setHeader(name, value);
  res.end(JSON.stringify(body));
}

function cleanText(value, max = MAX_TEXT) {
  return typeof value === 'string' && value.length <= max ? value : undefined;
}

function sanitizeRecord(input) {
  if (!input || typeof input !== 'object' || Array.isArray(input)) return null;
  const output = {};
  for (const field of ALLOWED_FIELDS) {
    const value = input[field];
    if (Array.isArray(value) && (field === 'reportedFindings' || field === 'carePlan')) {
      if (value.length > MAX_LIST_ITEMS) return null;
      const clean = value.map(item => cleanText(item, 500));
      if (clean.some(item => item === undefined)) return null;
      output[field] = clean;
    } else {
      const clean = cleanText(value);
      if (clean !== undefined) output[field] = clean;
      else if (value !== undefined) return null;
    }
  }
  if (output.region !== 'left-first-mtp' || !output.label) return null;
  output.bodyLikeness = PRIVATE_BODY_LIKENESS;
  return output;
}

module.exports = async function handler(req, res) {
  if (req.method !== 'GET') return respond(res, 405, { error: 'Method not allowed' }, { Allow: 'GET' });
  if (!requestOriginAllowed(req)) return respond(res, 403, { error: 'Forbidden' });
  if (!verifySession(req.headers.cookie, process.env.NOS_AUTH_SECRET || '')) {
    return respond(res, 401, { error: 'Authentication required' });
  }

  const raw = process.env.HEALTH_RECORD_JSON || '';
  if (!raw || Buffer.byteLength(raw) > MAX_ENV_BYTES) return respond(res, 503, { error: 'Health record unavailable' });
  let parsed;
  try { parsed = JSON.parse(raw); }
  catch { return respond(res, 503, { error: 'Health record unavailable' }); }
  const record = sanitizeRecord(parsed);
  if (!record) return respond(res, 503, { error: 'Health record unavailable' });
  return respond(res, 200, { record });
};

module.exports.sanitizeRecord = sanitizeRecord;
