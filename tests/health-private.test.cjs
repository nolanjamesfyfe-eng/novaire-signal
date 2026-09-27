'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const { Readable } = require('node:stream');
const { spawnSync } = require('node:child_process');
const path = require('node:path');

const auth = require('../api/health-auth');
const record = require('../api/health-record');
const session = require('../lib/health-session');

function request(method, { body = '', headers = {}, ip = '203.0.113.8' } = {}) {
  const req = Readable.from(body ? [body] : []);
  req.method = method;
  req.headers = { host: 'signal.example', origin: 'https://signal.example', 'x-forwarded-proto': 'https', ...headers };
  req.socket = { remoteAddress: ip };
  return req;
}

function response() {
  return {
    statusCode: 200, headers: {}, body: '',
    setHeader(name, value) { this.headers[name.toLowerCase()] = value; },
    end(value = '') { this.body = value; }
  };
}

async function invoke(handler, req) {
  const res = response();
  await handler(req, res);
  return res;
}

const originalEnv = { ...process.env };
test.beforeEach(() => {
  process.env.NOS_AUTH_SECRET = 'test-secret-that-is-not-deployed';
  process.env.NOS_ACCESS_PIN = '12345';
  process.env.HEALTH_RECORD_JSON = JSON.stringify({
    region: 'left-first-mtp', label: 'Left first MTP', summary: 'PRIVATE_SENTINEL',
    reportedFindings: ['Reported item'], carePlan: ['Care item'], sourceDate: '2026-09-27', certainty: 'Clinician supplied'
  });
});
test.after(() => { process.env = originalEnv; });

test('anonymous record request is denied without leaking the configured record', async () => {
  const res = await invoke(record, request('GET'));
  assert.equal(res.statusCode, 401);
  assert.equal(res.body.includes('PRIVATE_SENTINEL'), false);
  assert.match(res.headers['cache-control'], /no-store/);
  assert.match(res.headers['x-robots-tag'], /noindex/);
});

test('correct existing Signal PIN creates scoped cookie and unlocks sanitized record', async () => {
  const login = await invoke(auth, request('POST', { body: JSON.stringify({ pin: '12345' }) }));
  assert.equal(login.statusCode, 200);
  const setCookie = login.headers['set-cookie'];
  assert.match(setCookie, /^novaire_health_session=/);
  assert.match(setCookie, /Path=\/api/);
  assert.match(setCookie, /HttpOnly/);
  assert.match(setCookie, /Secure/);
  assert.match(setCookie, /SameSite=Strict/);
  const cookie = setCookie.split(';')[0];
  const unlocked = await invoke(record, request('GET', { headers: { cookie } }));
  assert.equal(unlocked.statusCode, 200);
  const parsed = JSON.parse(unlocked.body);
  assert.equal(parsed.record.region, 'left-first-mtp');
  assert.equal(parsed.record.summary, 'PRIVATE_SENTINEL');
  assert.deepEqual(Object.keys(parsed.record), ['region', 'label', 'summary', 'reportedFindings', 'carePlan', 'sourceDate', 'certainty', 'bodyLikeness']);
  assert.match(parsed.record.bodyLikeness.anatomicalLeftClavicle, /Self-reported/);
  assert.match(parsed.record.bodyLikeness.modelingCertainty, /Approximate/);
});

test('expired and tampered audience-bound sessions are rejected', async () => {
  const now = Math.floor(Date.now() / 1000);
  const expired = `${session.COOKIE_NAME}=${session.createSessionValue(process.env.NOS_AUTH_SECRET, now - session.MAX_AGE - 1)}`;
  assert.equal((await invoke(record, request('GET', { headers: { cookie: expired } }))).statusCode, 401);

  const current = session.createSessionValue(process.env.NOS_AUTH_SECRET, now);
  const tampered = `${session.COOKIE_NAME}=${current.slice(0, -1)}${current.endsWith('A') ? 'B' : 'A'}`;
  assert.equal((await invoke(record, request('GET', { headers: { cookie: tampered } }))).statusCode, 401);
});

test('cross-origin and missing browser provenance are rejected', async () => {
  const hostile = await invoke(auth, request('POST', { body: '{"pin":"12345"}', headers: { origin: 'https://evil.example' } }));
  assert.equal(hostile.statusCode, 403);
  const absent = await invoke(record, request('GET', { headers: { origin: undefined } }));
  assert.equal(absent.statusCode, 403);
  const fetchMetadata = await invoke(record, request('GET', { headers: { origin: undefined, 'sec-fetch-site': 'same-origin' } }));
  assert.equal(fetchMetadata.statusCode, 401);
});

test('oversized login payload and invalid record shape fail closed', async () => {
  const tooLarge = await invoke(auth, request('POST', { body: JSON.stringify({ pin: '1'.repeat(1100) }), ip: '203.0.113.44' }));
  assert.equal(tooLarge.statusCode, 413);
  process.env.HEALTH_RECORD_JSON = JSON.stringify({ region: 'left-first-mtp', label: 'x', summary: 'x'.repeat(2001) });
  const cookie = `${session.COOKIE_NAME}=${session.createSessionValue(process.env.NOS_AUTH_SECRET)}`;
  assert.equal((await invoke(record, request('GET', { headers: { cookie } }))).statusCode, 503);
});

test('logout expires cookie and frontend source parses', async () => {
  const logout = await invoke(auth, request('DELETE'));
  assert.equal(logout.statusCode, 200);
  assert.match(logout.headers['set-cookie'], /Max-Age=0/);
  const source = path.join(__dirname, '..', 'health', 'private-health.js');
  const checked = spawnSync(process.execPath, ['--check', source], { encoding: 'utf8' });
  assert.equal(checked.status, 0, checked.stderr);
});
