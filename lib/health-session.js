'use strict';

const crypto = require('node:crypto');

const COOKIE_NAME = 'novaire_health_session';
const AUDIENCE = 'health-record';
const MAX_AGE = 30 * 60;

function safeEqual(left, right) {
  const a = Buffer.from(String(left));
  const b = Buffer.from(String(right));
  return a.length === b.length && crypto.timingSafeEqual(a, b);
}

function encode(value) {
  return Buffer.from(JSON.stringify(value)).toString('base64url');
}

function sign(payload, secret) {
  return crypto.createHmac('sha256', secret).update(payload).digest('base64url');
}

function createSessionValue(secret, nowSeconds = Math.floor(Date.now() / 1000)) {
  if (!secret) throw new Error('Missing session secret');
  const payload = encode({
    aud: AUDIENCE,
    iat: nowSeconds,
    exp: nowSeconds + MAX_AGE,
    nonce: crypto.randomBytes(18).toString('base64url')
  });
  return `${payload}.${sign(payload, secret)}`;
}

function sessionCookie(secret, nowSeconds) {
  return `${COOKIE_NAME}=${createSessionValue(secret, nowSeconds)}; Path=/api; Max-Age=${MAX_AGE}; HttpOnly; Secure; SameSite=Strict`;
}

function clearSessionCookie() {
  return `${COOKIE_NAME}=; Path=/api; Max-Age=0; HttpOnly; Secure; SameSite=Strict`;
}

function readCookie(header) {
  for (const part of String(header || '').split(';')) {
    const separator = part.indexOf('=');
    if (separator > 0 && part.slice(0, separator).trim() === COOKIE_NAME) {
      return part.slice(separator + 1).trim();
    }
  }
  return '';
}

function verifySession(cookieHeader, secret, nowSeconds = Math.floor(Date.now() / 1000)) {
  if (!secret) return false;
  const value = readCookie(cookieHeader);
  const separator = value.lastIndexOf('.');
  if (separator < 1) return false;
  const payload = value.slice(0, separator);
  const signature = value.slice(separator + 1);
  if (!safeEqual(signature, sign(payload, secret))) return false;
  try {
    const data = JSON.parse(Buffer.from(payload, 'base64url').toString('utf8'));
    return data.aud === AUDIENCE &&
      Number.isInteger(data.iat) && Number.isInteger(data.exp) &&
      data.iat <= nowSeconds + 30 && data.exp >= nowSeconds &&
      data.exp - data.iat === MAX_AGE &&
      typeof data.nonce === 'string' && /^[A-Za-z0-9_-]{20,40}$/.test(data.nonce);
  } catch {
    return false;
  }
}

function requestOriginAllowed(req) {
  const headers = req.headers || {};
  const host = String(headers['x-forwarded-host'] || headers.host || '').split(',')[0].trim().toLowerCase();
  if (!host || /[\\/\s]/.test(host)) return false;
  const protocol = String(headers['x-forwarded-proto'] || 'https').split(',')[0].trim().toLowerCase();
  if (protocol !== 'https' && !(protocol === 'http' && /^(localhost|127\.0\.0\.1)(:\d+)?$/.test(host))) return false;
  const expected = `${protocol}://${host}`;
  const origin = headers.origin;
  if (typeof origin === 'string' && origin !== expected) return false;
  const fetchSite = String(headers['sec-fetch-site'] || '').toLowerCase();
  if (fetchSite && fetchSite !== 'same-origin') return false;
  return typeof origin === 'string' || fetchSite === 'same-origin';
}

module.exports = {
  AUDIENCE, COOKIE_NAME, MAX_AGE, clearSessionCookie, createSessionValue,
  requestOriginAllowed, safeEqual, sessionCookie, verifySession
};
