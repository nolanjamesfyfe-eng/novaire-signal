'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const { Readable } = require('node:stream');
const { DatabaseSync } = require('node:sqlite');

const streak = require('../lib/study-streak');
const store = require('../lib/study-streak-store');
const api = require('../api/study-streak');
const authApi = require('../api/study-auth');
const healthSession = require('../lib/health-session');
const studySession = require('../lib/study-session');

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
async function callAuth(req) { const res = response(); await authApi(req, res); return res; }
function healthCookie(secret = 'secret') { return `${healthSession.COOKIE_NAME}=${healthSession.createSessionValue(secret)}`; }
function studyCookie(secret = 'secret', now) { return `${studySession.COOKIE_NAME}=${studySession.createSessionValue(secret, now)}`; }
function configureRedis(document = null) {
  process.env.NOS_AUTH_SECRET = 'secret';
  process.env.KV_REST_API_URL = 'https://private.invalid';
  process.env.KV_REST_API_TOKEN = 'hidden';
  const commands = [];
  global.fetch = async (_url, options) => {
    const command = JSON.parse(options.body); commands.push(command);
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
  return { commands, get document() { return document; } };
}

test('a first click starts one and repeat-day data stays deduplicated', () => {
  const result = streak.summarize({ clickDates: ['2026-10-21', '2026-10-21'], startedAt: '2026-10-21' }, '2026-10-21');
  assert.equal(result.todayClicked, true);
  assert.equal(result.streak, 1);
  assert.equal(result.missedDays, 0);
});

test('today pending retains yesterday streak until an entire Bangkok day is missed', () => {
  const result = streak.summarize({ clickDates: ['2026-10-19', '2026-10-20'], startedAt: '2026-10-19' }, '2026-10-21');
  assert.equal(result.todayClicked, false);
  assert.equal(result.streak, 2);
  assert.equal(result.missedDays, 0);
});

test('zero, one, two and three completed misses exclude today and pre-launch dates', () => {
  assert.equal(streak.summarize({ clickDates: [], startedAt: '2026-10-21' }, '2026-10-21').missedDays, 0);
  assert.equal(streak.summarize({ clickDates: [], startedAt: '2026-10-21' }, '2026-10-22').missedDays, 1);
  assert.equal(streak.summarize({ clickDates: [], startedAt: '2026-10-21' }, '2026-10-23').missedDays, 2);
  assert.equal(streak.summarize({ clickDates: [], startedAt: '2026-10-21' }, '2026-10-24').missedDays, 3);
});

test('a click after a gap restarts at one and clears the missed warning', () => {
  const result = streak.summarize({ clickDates: ['2026-10-21', '2026-10-24'], startedAt: '2026-10-21' }, '2026-10-24');
  assert.equal(result.streak, 1);
  assert.equal(result.missedDays, 0);
});

test('Bangkok date rolls at 17:00 UTC rather than client timezone', () => {
  assert.equal(streak.bangkokDate(new Date('2026-10-20T16:59:59.999Z')), '2026-10-20');
  assert.equal(streak.bangkokDate(new Date('2026-10-20T17:00:00.000Z')), '2026-10-21');
});

test('unauthenticated device can mark today only; backfill and cross-origin are rejected', async () => {
  configureRedis(JSON.stringify({ revision: 1, startedAt: '2026-10-21', clickDates: [] }));
  const today = streak.bangkokDate(new Date());
  let res = await call(request('POST', { body: JSON.stringify({ action: 'merge', localDates: ['2026-10-22'] }) }));
  assert.equal(res.statusCode, 401);
  res = await call(request('POST', { body: JSON.stringify({ action: 'click', localDates: ['2026-10-22'] }) }));
  assert.equal(res.statusCode, 200);
  const body = JSON.parse(res.body);
  assert.equal(body.access, 'public-read');
  assert.equal(body.todayClicked, true);
  assert.equal(body.streak, 1);
  assert.equal(body.clickDates, undefined);
  assert.equal(body.today, today);
  res = await call(request('POST', { cookie: studyCookie(), headers: { origin: 'https://evil.example' }, body: '{}' }));
  assert.equal(res.statusCode, 403);
});

test('existing health session seamlessly mints a narrow durable study cookie and GET stays read-only', async () => {
  const backend = configureRedis();
  const res = await call(request('GET', { cookie: healthCookie() }));
  assert.equal(res.statusCode, 200);
  assert.equal(backend.commands.filter(command => command[0] === 'EVAL').length, 0);
  assert.match(res.headers['set-cookie'], /^novaire_study_session=/);
  assert.match(res.headers['set-cookie'], /Path=\/api\/study-streak/);
  assert.match(res.headers['set-cookie'], /Max-Age=7776000/);
  assert.match(res.headers['set-cookie'], /HttpOnly; Secure; SameSite=Strict/);
});

test('remembered study cookie works alone, while an expired one falls back to 401', async () => {
  configureRedis();
  let res = await call(request('GET', { cookie: studyCookie() }));
  assert.equal(res.statusCode, 200);
  const expiredAt = Math.floor(Date.now() / 1000) - studySession.MAX_AGE - 60;
  res = await call(request('POST', { cookie: studyCookie('secret', expiredAt), body: JSON.stringify({ action: 'merge', localDates: [] }) }));
  assert.equal(res.statusCode, 401);
});

test('one-time study connect issues only the narrow study cookie', async () => {
  process.env.NOS_AUTH_SECRET = 'secret';
  process.env.NOS_ACCESS_PIN = '12345';
  let res = await callAuth(request('POST', { body: JSON.stringify({ pin: '12345' }) }));
  assert.equal(res.statusCode, 200);
  assert.match(res.headers['set-cookie'], /^novaire_study_session=/);
  assert.match(res.headers['set-cookie'], /Path=\/api\/study-streak/);
  assert.doesNotMatch(res.headers['set-cookie'], /novaire_health_session|novaire_portfolio_session/);
  res = await callAuth(request('POST', { body: JSON.stringify({ pin: '54321' }) }));
  assert.equal(res.statusCode, 401);
  res = await callAuth(request('POST', { body: JSON.stringify({ pin: '12345' }), headers: { origin: 'https://evil.example' } }));
  assert.equal(res.statusCode, 403);
});

test('authenticated click plus queued local dates merge, sort and deduplicate', async () => {
  const backend = configureRedis(JSON.stringify({ revision: 1, startedAt: '2026-10-21', clickDates: ['2026-10-21'] }));
  const today = streak.bangkokDate(new Date());
  const future = streak.shiftDate(today, 1);
  const res = await call(request('POST', { cookie: studyCookie(), body: JSON.stringify({ action: 'click', localDates: ['2026-10-21', '2026-10-21', future] }) }));
  assert.equal(res.statusCode, 200);
  const stored = JSON.parse(backend.document);
  assert.deepEqual(stored.clickDates, [...new Set(['2026-10-21', today])].sort());
  assert.deepEqual(JSON.parse(res.body).clickDates, stored.clickDates);
});

test('merge drops out-of-range clock skew but rejects malformed and oversized histories', async () => {
  const backend = configureRedis();
  const future = streak.shiftDate(streak.bangkokDate(new Date()), 1);
  for (const dates of [['2026-10-20'], [future]]) {
    const res = await call(request('POST', { cookie: studyCookie(), body: JSON.stringify({ action: 'merge', localDates: dates }) }));
    assert.equal(res.statusCode, 200);
  }
  for (const dates of [['2026-99-99'], Array(4097).fill('2026-10-21')]) {
    const res = await call(request('POST', { cookie: studyCookie(), body: JSON.stringify({ action: 'merge', localDates: dates }) }));
    assert.equal(res.statusCode, 400);
  }
  assert.equal(backend.commands.filter(command => command[0] === 'EVAL').length, 0);
});

test('D1 compare-and-set advances twice and rejects a stale revision', () => {
  const db = new DatabaseSync(':memory:');
  db.exec('CREATE TABLE health_checkin_documents (storage_key TEXT PRIMARY KEY, revision INTEGER NOT NULL, payload TEXT NOT NULL, updated_at TEXT NOT NULL)');
  const cas = db.prepare(store.D1_CAS_SQL), key = 'isolated-study-streak-test';
  const first = JSON.stringify({ revision: 1, startedAt: '2026-10-21', clickDates: ['2026-10-21'] });
  const second = JSON.stringify({ revision: 2, startedAt: '2026-10-21', clickDates: ['2026-10-21', '2026-10-22'] });
  const run = (expected, revision, payload) => cas.run(key, revision, payload, new Date().toISOString(), expected, key, expected, expected);
  assert.equal(Number(run(0, 1, first).changes), 1);
  assert.equal(Number(run(1, 2, second).changes), 1);
  assert.equal(Number(run(1, 3, '{}').changes), 0);
  assert.equal(db.prepare('SELECT payload FROM health_checkin_documents WHERE storage_key = ?').get(key).payload, second);
  db.close();
});

test('concurrent click merges produce one stored date', async () => {
  const backend = configureRedis();
  const [a, b] = await Promise.all([store.mergeClickDates(['2026-10-21']), store.mergeClickDates(['2026-10-21'])]);
  assert.equal([a.deduplicated, b.deduplicated].filter(Boolean).length, 1);
  assert.deepEqual(JSON.parse(backend.document).clickDates, ['2026-10-21']);
});

test('unconnected GET returns read-only streak summary without click dates or writes', async () => {
  const backend = configureRedis();
  const res = await call(request('GET'));
  assert.equal(res.statusCode, 200);
  const body = JSON.parse(res.body);
  assert.equal(body.access, 'public-read');
  assert.equal(body.clickDates, undefined);
  assert.equal(typeof body.streak, 'number');
  assert.equal(backend.commands.filter(command => command[0] === 'EVAL').length, 0);
  assert.equal(res.headers['set-cookie'], undefined);
});
