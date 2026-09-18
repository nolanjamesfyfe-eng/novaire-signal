const test = require('node:test');
const assert = require('node:assert/strict');
const { compactPopulation, compactGDP } = require('../map/fact_format.js');

test('GDP formatting scales IMF billions into T/B/M', () => {
  assert.equal(compactGDP(30767.075), '$30.8T');
  assert.equal(compactGDP(2319.9), '$2.3T');
  assert.equal(compactGDP(920.05), '$920B');
  assert.equal(compactGDP(0.245), '$245M');
  assert.equal(compactGDP(null), 'N/A');
});

test('population formatting preserves established display contract', () => {
  assert.equal(compactPopulation(1463865525), '1.5B');
  assert.equal(compactPopulation(42000000), '42M');
  assert.equal(compactPopulation(82904), '83K');
  assert.equal(compactPopulation(undefined), 'Unavailable');
});
