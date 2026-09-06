import assert from 'node:assert/strict';
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = fileURLToPath(new URL('.', import.meta.url));
const html = readFileSync(join(root, 'index.html'), 'utf8');
const js = readFileSync(join(root, 'app.js'), 'utf8');

assert.match(html, /name="referrer" content="no-referrer"/);
assert.match(html, /name="robots" content="noindex,nofollow,noarchive"/);
assert.match(html, /@font-face/);
assert.doesNotMatch(html + js, /https?:\/\//, 'studio must not reference external assets');
assert.match(js, /x: \[1600, 900\]/);
assert.match(js, /story: \[1080, 1920\]/);
assert.match(js, /document\.fonts\.ready/);
assert.match(js, /confirmation: true, requestId/);
assert.match(js, /fetch\('\/api\/quote-auth'/);
assert.match(js, /fetch\('\/api\/quote-post'/);
assert.match(js, /Nothing was retried automatically/);
assert.doesNotMatch(js, /localStorage|sessionStorage/);
assert.match(js, /\[\.\.\.text\]\.length > 280/);
assert.equal((js.match(/\{ text: '/g) || []).length, 14, 'expected curated source quote count');
assert.equal((html.match(/data-style=/g) || []).length, 2, 'expected two standalone style controls');
for (const font of readdirSync(join(root, 'fonts')).filter(f => f.endsWith('.woff2'))) assert.ok(statSync(join(root, 'fonts', font)).size > 20_000, `${font} should be a real vendored font`);
console.log('quote-studio contracts: ok (2 designs, 14 source quotes, 2 export sizes, local fonts)');
