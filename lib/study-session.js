'use strict';

const crypto = require('node:crypto');

const COOKIE_NAME = 'novaire_study_session';
const AUDIENCE = 'anki-click-days';
const MAX_AGE = 90 * 24 * 60 * 60;
const COOKIE_PATH = '/api/study-streak';

function safeEqual(left, right) {
  const a = Buffer.from(String(left));
  const b = Buffer.from(String(right));
  return a.length === b.length && crypto.timingSafeEqual(a, b);
}
function encode(value) { return Buffer.from(JSON.stringify(value)).toString('base64url'); }
function sign(payload, secret) { return crypto.createHmac('sha256', secret).update(payload).digest('base64url'); }
function createSessionValue(secret, nowSeconds = Math.floor(Date.now() / 1000)) {
  if (!secret) throw new Error('Missing session secret');
  const payload = encode({ aud: AUDIENCE, iat: nowSeconds, exp: nowSeconds + MAX_AGE, nonce: crypto.randomBytes(18).toString('base64url') });
  return `${payload}.${sign(payload, secret)}`;
}
function sessionCookie(secret, nowSeconds) {
  return `${COOKIE_NAME}=${createSessionValue(secret, nowSeconds)}; Path=${COOKIE_PATH}; Max-Age=${MAX_AGE}; HttpOnly; Secure; SameSite=Strict`;
}
function clearSessionCookie() {
  return `${COOKIE_NAME}=; Path=${COOKIE_PATH}; Max-Age=0; HttpOnly; Secure; SameSite=Strict`;
}
function readCookie(header) {
  for (const part of String(header || '').split(';')) {
    const separator = part.indexOf('=');
    if (separator > 0 && part.slice(0, separator).trim() === COOKIE_NAME) return part.slice(separator + 1).trim();
  }
  return '';
}
function verifySession(cookieHeader, secret, nowSeconds = Math.floor(Date.now() / 1000)) {
  if (!secret) return false;
  const value = readCookie(cookieHeader), separator = value.lastIndexOf('.');
  if (separator < 1) return false;
  const payload = value.slice(0, separator), signature = value.slice(separator + 1);
  if (!safeEqual(signature, sign(payload, secret))) return false;
  try {
    const data = JSON.parse(Buffer.from(payload, 'base64url').toString('utf8'));
    return data.aud === AUDIENCE && Number.isInteger(data.iat) && Number.isInteger(data.exp) &&
      data.iat <= nowSeconds + 30 && data.exp >= nowSeconds && data.exp - data.iat === MAX_AGE &&
      typeof data.nonce === 'string' && /^[A-Za-z0-9_-]{20,40}$/.test(data.nonce);
  } catch { return false; }
}

module.exports = { AUDIENCE, COOKIE_NAME, COOKIE_PATH, MAX_AGE, clearSessionCookie, createSessionValue, sessionCookie, verifySession };