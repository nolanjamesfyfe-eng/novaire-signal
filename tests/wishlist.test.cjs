const test = require('node:test');
const assert = require('node:assert/strict');
const { move, restore } = require('../map/wishlist.js');
const defaults = ['AR', 'CL', 'BR'];
const valid = new Set([...defaults, 'MN']);
test('move up/down or to a specific rank without mutating input', () => {
  assert.deepEqual(move(defaults, 2, 0), ['BR', 'AR', 'CL']);
  assert.deepEqual(move(defaults, 0, 2), ['CL', 'BR', 'AR']);
  assert.deepEqual(move(defaults, 1, 0), ['CL', 'AR', 'BR']);
  assert.deepEqual(defaults, ['AR', 'CL', 'BR']);
  assert.deepEqual(move(defaults, 0, -1), defaults);
  assert.deepEqual(move(defaults, 0, 3), defaults);
});
test('fresh ranking starts locked; saved order, additions and lock survive', () => {
  assert.deepEqual(restore(null, defaults, valid), { codes: defaults, locked: true });
  for (const locked of [true, false]) {
    const saved = { version: 1, codes: ['MN', 'BR', 'AR', 'CL'], locked };
    assert.deepEqual(restore(JSON.stringify(saved), defaults, valid), { codes: saved.codes, locked });
  }
  assert.deepEqual(restore('{"version":1,"codes":[],"locked":true}', defaults, valid), {codes: [], locked: true});
});
test('invalid and duplicate stored countries are rejected', () => {
  for (const codes of [['XX'], ['AR', 'AR'], ['<script>'], [1]]) {
    assert.throws(() => restore(JSON.stringify({ version: 1, codes, locked: true }), defaults, valid));
  }
  assert.throws(() => restore('oops', defaults, valid));
  assert.throws(() => restore('{}', defaults, valid));
});
