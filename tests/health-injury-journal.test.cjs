'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');

const journal = require('../health/injury-journal.js');

const valid = {
  schema: 'novaire.health.injury-journal', version: 1,
  injuries: [{ id:'inj-1', createdAt:'2026-09-27T10:00:00.000Z', status:'ongoing', severity:4, onset:'2026-09-20', mechanism:'Running', note:'Sore', point:{ x:1, y:2, z:3, structureKey:'bone-1', structureName:'Left first metatarsal bone', layer:'bone' } }],
  daily: [{ id:'day-1', date:'2026-09-27', sleepHours:7.5, sleepQuality:4, training:'Strength', lateMeal:true, mealTime:'22:15' }]
};

test('accepts the versioned local journal schema and returns a clean copy', () => {
  const result = journal.validateJournal(valid);
  assert.equal(result.ok, true);
  assert.notEqual(result.value, valid);
  assert.equal(result.value.injuries[0].point.structureName, 'Left first metatarsal bone');
});

test('rejects malformed imports instead of partially accepting them', () => {
  for (const bad of [null, {}, {...valid, version:2}, {...valid, injuries:[{...valid.injuries[0], severity:11}]}, {...valid, daily:[{...valid.daily[0], mealTime:'tomorrow'}]}]) {
    assert.equal(journal.validateJournal(bad).ok, false);
  }
});

test('association copy is observational and refuses to invent a trend', () => {
  assert.match(journal.describeAssociations([]), /Not enough logged days/i);
  const text = journal.describeAssociations(valid.daily);
  assert.match(text, /association/i);
  assert.doesNotMatch(text, /caus|leads to|because/i);
});

test('extracts authenticated injury records only from explicit injury fields', () => {
  const record = { label:'Unrelated record', injuries:[{ id:'clinical-1', label:'Fixture clavicle injury', region:'left-clavicle', year:'circa 2018', dateCertainty:'Self-reported approximate', provenance:'Synthetic fixture', summary:'Exact sites not recorded.' }] };
  const extracted=journal.extractRecordInjuries(record);
  assert.deepEqual(extracted.map(x=>x.region), ['left-clavicle']);
  assert.equal(extracted[0].year,'circa 2018');
  assert.equal(extracted[0].dateCertainty,'Self-reported approximate');
  assert.deepEqual(journal.extractRecordInjuries({region:'left-first-mtp',label:'Authenticated MTP record'}).map(x=>x.region), ['left-first-mtp']);
  assert.deepEqual(journal.extractRecordInjuries({ summary:'left foot hurts' }), []);
});
