'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');

const streak = require('../lib/study-streak');
const store = require('../lib/study-streak-store');
const api = require('../api/study-streak');
const session = require('../lib/health-session');
const { Readable } = require('node:stream');
const { DatabaseSync } = require('node:sqlite');

const originalEnv = { ...process.env };
test.afterEach(() => { process.env = { ...originalEnv }; delete global.fetch; });
function request(method, { body = '', cookie = '', headers = {} } = {}) {
  const req = Readable.from(body ? [body] : []);
  req.method = method;
  req.headers = { host: 'signal.example', origin: 'https://signal.example', 'x-forwarded-proto': 'https', cookie, ...headers };
  return req;
}
function response() { return { statusCode: 0, headers: {}, body: '', setHeader(k, v) { this.headers[k.toLowerCase()] = v; }, end(v = '') { this.body = v; } }; }
async function call(req) { const res = response(); await api(req, res); return res; }
function authenticatedCookie(secret = 'secret') { return `${session.COOKIE_NAME}=${session.createSessionValue(secret)}`; }

test('a first click starts a one-day Bangkok click streak', () => {
  const result = streak.summarize({ clickDates: ['2026-10-21'], startedAt: '2026-10-21' }, '2026-10-21');
  assert.equal(result.todayClicked, true);
  assert.equal(result.streak, 1);
});

test('today pending retains a consecutive streak through yesterday', () => {
  const result = streak.summarize({ clickDates: ['2026-10-19', '2026-10-20'], startedAt: '2026-10-19' }, '2026-10-21');
  assert.equal(result.todayClicked, false);
  assert.equal(result.streak, 2);
  assert.equal(result.todayStatus, 'pending');
});

test('a full missed Bangkok day resets the streak and the next click restarts at one', () => {
  assert.equal(streak.summarize({ clickDates: ['2026-10-18', '2026-10-19'], startedAt: '2026-10-18' }, '2026-10-21').streak, 0);
  assert.equal(streak.summarize({ clickDates: ['2026-10-18', '2026-10-19', '2026-10-21'], startedAt: '2026-10-18' }, '2026-10-21').streak, 1);
});

test('recent history begins at feature start and makes misses observable', () => {
  const result = streak.summarize({ clickDates: ['2026-10-19', '2026-10-21'], startedAt: '2026-10-19' }, '2026-10-21');
  assert.deepEqual(result.recentDays, [
    { date: '2026-10-19', status: 'clicked' },
    { date: '2026-10-20', status: 'missed' },
    { date: '2026-10-21', status: 'clicked' },
  ]);
});

test('Bangkok date rolls at 17:00 UTC rather than client timezone', () => {
  assert.equal(streak.bangkokDate(new Date('2026-10-20T16:59:59.999Z')), '2026-10-20');
  assert.equal(streak.bangkokDate(new Date('2026-10-20T17:00:00.000Z')), '2026-10-21');
});

test('streak endpoint rejects unauthenticated reads and cross-origin writes', async () => {
  process.env.NOS_AUTH_SECRET = 'secret';
  let res = await call(request('GET'));
  assert.equal(res.statusCode, 401);
  res = await call(request('POST', { cookie: authenticatedCookie(), headers: { origin: 'https://evil.example' } }));
  assert.equal(res.statusCode, 403);
});

test('authenticated GET is read-only and POST deduplicates the server Bangkok date', async () => {
  process.env.NOS_AUTH_SECRET = 'secret';
  process.env.KV_REST_API_URL = 'https://private.invalid';
  process.env.KV_REST_API_TOKEN = 'hidden';
  let document = null;
  const commands = [];
  global.fetch = async (_url, options) => {
    const command = JSON.parse(options.body); commands.push(command);
    if (command[0] === 'GET') return { ok: true, json: async () => ({ result: document }) };
    if (command[0] === 'EVAL') { document = command[5]; return { ok: true, json: async () => ({ result: 1 }) }; }
    throw new Error('unexpected command');
  };
  const cookie = authenticatedCookie();
  let res = await call(request('GET', { cookie }));
  assert.equal(res.statusCode, 200);
  assert.equal(commands.filter(command => command[0] === 'EVAL').length, 0);
  res = await call(request('POST', { cookie }));
  assert.equal(res.statusCode, 200);
  const first = JSON.parse(res.body);
  assert.equal(first.todayClicked, true);
  assert.equal(first.deduplicated, false);
  res = await call(request('POST', { cookie }));
  assert.equal(JSON.parse(res.body).deduplicated, true);
  assert.equal(JSON.parse(document).clickDates.length, 1);
});

test('D1 compare-and-set advances twice and rejects a stale revision', () => {
  const db = new DatabaseSync(':memory:');
  db.exec('CREATE TABLE health_checkin_documents (storage_key TEXT PRIMARY KEY, revision INTEGER NOT NULL, payload TEXT NOT NULL, updated_at TEXT NOT NULL)');
  const cas = db.prepare(store.D1_CAS_SQL);
  const key = 'isolated-study-streak-test';
  const first = JSON.stringify({ revision: 1, startedAt: '2026-10-21', clickDates: ['2026-10-21'] });
  const second = JSON.stringify({ revision: 2, startedAt: '2026-10-21', clickDates: ['2026-10-21', '2026-10-22'] });
  const stale = JSON.stringify({ revision: 3, startedAt: '2026-10-21', clickDates: ['2026-10-21', '2026-10-23'] });
  const run = (expected, revision, payload) => cas.run(key, revision, payload, new Date().toISOString(), expected, key, expected, expected);
  assert.equal(Number(run(0, 1, first).changes), 1);
  assert.equal(Number(run(1, 2, second).changes), 1);
  assert.equal(Number(run(1, 3, stale).changes), 0);
  assert.equal(db.prepare('SELECT revision, payload FROM health_checkin_documents WHERE storage_key = ?').get(key).revision, 2);
  assert.equal(db.prepare('SELECT payload FROM health_checkin_documents WHERE storage_key = ?').get(key).payload, second);
  db.close();
});

test('concurrent clicks across tabs produce one stored date', async () => {
  process.env.KV_REST_API_URL = 'https://private.invalid';
  process.env.KV_REST_API_TOKEN = 'hidden';
  let document = null;
  global.fetch = async (_url, options) => {
    const command = JSON.parse(options.body);
    if (command[0] === 'GET') return { ok: true, json: async () => ({ result: document }) };
    if (command[0] === 'EVAL') {
      const expected = Number(command[4]);
      const current = document ? JSON.parse(document).revision : 0;
      if (expected !== current) return { ok: true, json: async () => ({ result: 0 }) };
      document = command[5];
      return { ok: true, json: async () => ({ result: 1 }) };
    }
    throw new Error('unexpected command');
  };
  const [a, b] = await Promise.all([store.recordClick('2026-10-21'), store.recordClick('2026-10-21')]);
  assert.equal([a.deduplicated, b.deduplicated].filter(Boolean).length, 1);
  assert.deepEqual(JSON.parse(document).clickDates, ['2026-10-21']);
});
