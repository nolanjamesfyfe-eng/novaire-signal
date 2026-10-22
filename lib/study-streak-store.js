'use strict';

const { FEATURE_START_DATE } = require('./study-streak');
const TABLE = 'health_checkin_documents';
const DEFAULT_KEY = 'novaire:study:anki-click-days:v1';
const D1_CAS_SQL = `INSERT INTO ${TABLE} (storage_key, revision, payload, updated_at)
  SELECT ?, ?, ?, ? WHERE ? = 0 OR EXISTS (SELECT 1 FROM ${TABLE} WHERE storage_key = ? AND revision = ?)
  ON CONFLICT(storage_key) DO UPDATE SET
    revision = excluded.revision, payload = excluded.payload, updated_at = excluded.updated_at
  WHERE ${TABLE}.revision = ?`;

function storageKey() { return process.env.STUDY_STREAK_STORAGE_KEY || DEFAULT_KEY; }
function config() {
  const url = process.env.KV_REST_API_URL || process.env.UPSTASH_REDIS_REST_URL || '';
  const token = process.env.KV_REST_API_TOKEN || process.env.UPSTASH_REDIS_REST_TOKEN || '';
  if (url && token) return { kind: 'redis', url: url.replace(/\/$/, ''), token };
  const accountId = process.env.HEALTH_D1_ACCOUNT_ID || '';
  const databaseId = process.env.HEALTH_D1_DATABASE_ID || '';
  const apiToken = process.env.HEALTH_D1_API_TOKEN || '';
  if (accountId && databaseId && apiToken) return { kind: 'd1', url: `https://api.cloudflare.com/client/v4/accounts/${encodeURIComponent(accountId)}/d1/database/${encodeURIComponent(databaseId)}/query`, token: apiToken };
  return null;
}
function unavailable() { return Object.assign(new Error('Private study streak storage is unavailable.'), { code: 'UNAVAILABLE' }); }
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
function empty() { return { revision: 0, startedAt: FEATURE_START_DATE, clickDates: [] }; }
function parse(raw) {
  if (!raw) return empty();
  try {
    const value = JSON.parse(raw);
    if (!Number.isInteger(value.revision) || !/^\d{4}-\d{2}-\d{2}$/.test(value.startedAt) || !Array.isArray(value.clickDates)) throw new Error();
    value.clickDates = [...new Set(value.clickDates.filter(date => /^\d{4}-\d{2}-\d{2}$/.test(date) && date >= value.startedAt))].sort();
    return value;
  } catch { throw unavailable(); }
}
async function read() {
  const cfg = config(); if (!cfg) throw unavailable(); const key = storageKey();
  if (cfg.kind === 'redis') return parse(await redisCommand(cfg, ['GET', key]));
  const result = await d1Query(cfg, `SELECT payload FROM ${TABLE} WHERE storage_key = ?`, [key]);
  return parse((Array.isArray(result.results) ? result.results : [])[0]?.payload);
}
async function compareAndSet(expectedRevision, next) {
  const cfg = config(); if (!cfg) throw unavailable(); const key = storageKey(); const payload = JSON.stringify(next);
  if (cfg.kind === 'redis') {
    const script = "local raw=redis.call('GET',KEYS[1]); local rev=0; if raw then local ok,v=pcall(cjson.decode,raw); if not ok then return -2 end; rev=v['revision'] or -1 end; if rev~=tonumber(ARGV[1]) then return 0 end; redis.call('SET',KEYS[1],ARGV[2]); return 1";
    return Number(await redisCommand(cfg, ['EVAL', script, '1', key, String(expectedRevision), payload])) === 1;
  }
  const result = await d1Query(cfg, D1_CAS_SQL, [key, next.revision, payload, new Date().toISOString(), expectedRevision, key, expectedRevision, expectedRevision]);
  return Number(result.meta?.changes) === 1;
}
async function mergeClickDates(dates) {
  const incoming = [...new Set(dates)].sort();
  for (let attempt = 0; attempt < 4; attempt += 1) {
    const current = await read();
    const merged = [...new Set([...current.clickDates, ...incoming])].sort();
    if (merged.length === current.clickDates.length) return { document: current, deduplicated: true };
    const next = { ...current, revision: current.revision + 1, clickDates: merged, updatedAt: new Date().toISOString() };
    if (await compareAndSet(current.revision, next)) return { document: next, deduplicated: false };
  }
  throw Object.assign(new Error('Concurrent update could not be resolved.'), { code: 'CONFLICT' });
}

module.exports = { D1_CAS_SQL, compareAndSet, config, empty, mergeClickDates, parse, read };
