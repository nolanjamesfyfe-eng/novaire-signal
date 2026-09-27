'use strict';

const model = require('../health/checkin-model');
const DEFAULT_KEY = 'novaire:health:daily-checkins:v1';
const TABLE = 'health_checkin_documents';
const MAX_RECORDS = 800;
const MAX_BYTES = 900 * 1024;
const D1_CAS_SQL = `INSERT INTO ${TABLE} (storage_key, revision, payload, updated_at)
  SELECT ?, ?, ?, ? WHERE ? = 0 OR EXISTS (SELECT 1 FROM health_checkin_documents WHERE storage_key = ? AND revision = ?)
  ON CONFLICT(storage_key) DO UPDATE SET
    revision = excluded.revision, payload = excluded.payload, updated_at = excluded.updated_at
  WHERE ${TABLE}.revision = ?`;

function storageKey() { return process.env.HEALTH_CHECKIN_STORAGE_KEY || DEFAULT_KEY; }

function config() {
  const redisUrl = process.env.KV_REST_API_URL || process.env.UPSTASH_REDIS_REST_URL || '';
  const redisToken = process.env.KV_REST_API_TOKEN || process.env.UPSTASH_REDIS_REST_TOKEN || '';
  if (redisUrl && redisToken) return { kind: 'redis', url: redisUrl.replace(/\/$/, ''), token: redisToken };
  const accountId = process.env.HEALTH_D1_ACCOUNT_ID || '';
  const databaseId = process.env.HEALTH_D1_DATABASE_ID || '';
  const token = process.env.HEALTH_D1_API_TOKEN || '';
  if (accountId && databaseId && token) return {
    kind: 'd1',
    url: `https://api.cloudflare.com/client/v4/accounts/${encodeURIComponent(accountId)}/d1/database/${encodeURIComponent(databaseId)}/query`,
    token
  };
  return null;
}

function unavailable() {
  return Object.assign(new Error('Private check-in storage is unavailable.'), { code: 'UNAVAILABLE' });
}
async function redisCommand(cfg, args) {
  const response = await fetch(cfg.url, { method: 'POST', headers: { Authorization: `Bearer ${cfg.token}`, 'Content-Type': 'application/json' }, body: JSON.stringify(args), cache: 'no-store' });
  if (!response.ok) throw unavailable();
  const body = await response.json();
  if (body.error) throw unavailable();
  return body.result;
}
async function d1Query(cfg, sql, params = []) {
  const response = await fetch(cfg.url, { method: 'POST', headers: { Authorization: `Bearer ${cfg.token}`, 'Content-Type': 'application/json' }, body: JSON.stringify({ sql, params }), cache: 'no-store' });
  if (!response.ok) throw unavailable();
  const body = await response.json();
  const result = body.success && Array.isArray(body.result) ? body.result[0] : null;
  if (!result || result.success === false) throw unavailable();
  return result;
}
function empty() { return { revision: 0, entries: [] }; }
function parseDocument(raw) {
  if (!raw) return empty();
  try {
    const value = JSON.parse(raw);
    if (!Number.isInteger(value.revision) || !Array.isArray(value.entries)) throw new Error();
    return value;
  } catch { throw Object.assign(new Error('Stored check-ins are invalid.'), { code: 'UNAVAILABLE' }); }
}
async function read() {
  const cfg = config();
  if (!cfg) throw Object.assign(new Error('Private check-in storage is not configured.'), { code: 'UNAVAILABLE' });
  const key = storageKey();
  if (cfg.kind === 'redis') return parseDocument(await redisCommand(cfg, ['GET', key]));
  const result = await d1Query(cfg, `SELECT payload FROM ${TABLE} WHERE storage_key = ?`, [key]);
  const rows = Array.isArray(result.results) ? result.results : [];
  return parseDocument(rows[0]?.payload);
}
async function compareAndSet(expectedRevision, next) {
  const payload = JSON.stringify(next);
  if (Buffer.byteLength(payload) > MAX_BYTES || next.entries.length > MAX_RECORDS) throw Object.assign(new Error('Check-in storage limit reached.'), { code: 'LIMIT' });
  const cfg = config();
  if (!cfg) throw Object.assign(new Error('Private check-in storage is not configured.'), { code: 'UNAVAILABLE' });
  const key = storageKey();
  if (cfg.kind === 'redis') {
    const script = "local raw=redis.call('GET',KEYS[1]); local rev=0; if raw then local ok,v=pcall(cjson.decode,raw); if not ok then return -2 end; rev=v['revision'] or -1 end; if rev~=tonumber(ARGV[1]) then return 0 end; redis.call('SET',KEYS[1],ARGV[2]); return 1";
    const result = await redisCommand(cfg, ['EVAL', script, '1', key, String(expectedRevision), payload]);
    return Number(result) === 1;
  }
  const result = await d1Query(cfg, D1_CAS_SQL, [key, next.revision, payload, new Date().toISOString(), expectedRevision, key, expectedRevision, expectedRevision]);
  return Number(result.meta?.changes) === 1;
}
function sanitize(input, today = model.bangkokDate()) {
  if (!input || typeof input !== 'object' || Array.isArray(input)) return null;
  // Legacy 0-5/schema-v1 values require an explicit scale migration; never rescore them as v2.
  if (input.scaleMax === 5 || input.schemaVersion === 1) return null;
  const date = input.date;
  if (!model.parseDate(date) || date < '2020-01-01' || date > today) return null;
  const answers = {};
  for (const key of model.SUBJECTIVE_KEYS) {
    const n = input.answers?.[key]; if (!Number.isInteger(n) || n < 0 || n > 10) return null; answers[key] = n;
  }
  const out = { date, calculationVersion: model.VERSION, scaleMax: 10, score: model.subjectiveScore(answers), answers };
  const f = input.foundations || {}, clean = {};
  if (f.anki !== undefined) { if (!['no','partial','complete'].includes(f.anki)) return null; clean.anki = f.anki; }
  if (f.body !== undefined) { if (!['none','recovery','workout'].includes(f.body)) return null; clean.body = f.body; }
  const nums = { sleepHours:[0,24], sleepQuality:[0,10], proteinGrams:[0,1000], proteinTarget:[1,1000], balancedDiet:[0,10], fluidsLiters:[0,20], fluidsTarget:[.1,20], alcoholCount:[0,100], skinComfort:[0,10], skinIrritation:[0,10], skinDryness:[0,10] };
  for (const [key,[min,max]] of Object.entries(nums)) if (f[key] !== undefined && f[key] !== '') { const n=Number(f[key]); if (!Number.isFinite(n)||n<min||n>max) return null; clean[key]=n; }
  for (const key of ['foodNotes','heatExerciseNote']) if (f[key] !== undefined && f[key] !== '') { if(typeof f[key] !== 'string'||f[key].length>500)return null;clean[key]=f[key]; }
  out.foundations = clean;
  if (typeof input.clientUpdatedAt === 'string' && /^\d{4}-\d\d-\d\dT/.test(input.clientUpdatedAt) && input.clientUpdatedAt.length <= 40) out.clientUpdatedAt = input.clientUpdatedAt;
  return out;
}
module.exports = { D1_CAS_SQL, MAX_RECORDS, compareAndSet, config, empty, read, sanitize };
