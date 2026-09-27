(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.HealthCheckinModel = api;
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';
  const VERSION = 3;
  const SUBJECTIVE_KEYS = ['energy', 'focus', 'stress', 'calm', 'happiness'];
  const FOUNDATION_NUMBERS = {
    sleepHours: [0, 24], sleepQuality: [0, 10], proteinGrams: [0, 1000], proteinTarget: [1, 1000],
    balancedDiet: [0, 10], fluidsLiters: [0, 20], fluidsTarget: [.1, 20], alcoholCount: [0, 100],
    skinComfort: [0, 10], skinIrritation: [0, 10], skinDryness: [0, 10]
  };
  const pad = n => String(n).padStart(2, '0');
  function bangkokDate(now = new Date()) {
    const parts = new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Bangkok', year: 'numeric', month: '2-digit', day: '2-digit' }).formatToParts(now);
    const get = type => parts.find(p => p.type === type).value;
    return `${get('year')}-${get('month')}-${get('day')}`;
  }
  function parseDate(value) {
    const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value || '');
    if (!match) return null;
    const d = new Date(Date.UTC(+match[1], +match[2] - 1, +match[3]));
    return d.getUTCFullYear() === +match[1] && d.getUTCMonth() === +match[2] - 1 && d.getUTCDate() === +match[3] ? d : null;
  }
  const iso = d => `${d.getUTCFullYear()}-${pad(d.getUTCMonth() + 1)}-${pad(d.getUTCDate())}`;
  function period(date, view) {
    const d = parseDate(date); if (!d) throw new Error('Invalid date');
    if (view === 'day') return { start: date, end: date, days: 1 };
    if (view === 'week') {
      const start = new Date(d); start.setUTCDate(d.getUTCDate() - ((d.getUTCDay() + 6) % 7));
      const end = new Date(start); end.setUTCDate(start.getUTCDate() + 6);
      return { start: iso(start), end: iso(end), days: 7 };
    }
    const start = new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), 1));
    const end = new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth() + 1, 0));
    return { start: iso(start), end: iso(end), days: end.getUTCDate() };
  }
  function subjectiveScore(answers) {
    if (!answers || SUBJECTIVE_KEYS.some(k => !Number.isFinite(answers[k]) || answers[k] < 0 || answers[k] > 10)) return null;
    return Math.round(((answers.energy + answers.focus + (10 - answers.stress) + answers.calm + answers.happiness) / 50) * 100);
  }
  function foundations(f = {}) {
    const items = [], add = (key, label, earned, possible = 1) => items.push({ key, label, earned, possible });
    if (['no', 'partial', 'complete'].includes(f.anki)) add('anki', 'Brain · Anki', { no: 0, partial: .5, complete: 1 }[f.anki]);
    if (['none', 'recovery', 'workout'].includes(f.body)) add('body', 'Body', f.body === 'none' ? 0 : 1);
    if (Number.isFinite(f.sleepHours)) add('sleepHours', 'Sleep duration', Math.min(Math.max(f.sleepHours, 0) / 8, 1));
    if (Number.isFinite(f.sleepQuality)) add('sleepQuality', 'Sleep quality', Math.min(Math.max(f.sleepQuality, 0), 10) / 10);
    if (Number.isFinite(f.proteinGrams) && Number.isFinite(f.proteinTarget) && f.proteinTarget > 0) add('protein', 'Protein', Math.min(Math.max(f.proteinGrams, 0) / f.proteinTarget, 1));
    if (Number.isFinite(f.balancedDiet)) add('balancedDiet', 'Balanced diet', Math.min(Math.max(f.balancedDiet, 0), 10) / 10);
    if (Number.isFinite(f.fluidsLiters) && Number.isFinite(f.fluidsTarget) && f.fluidsTarget > 0) add('fluids', 'Nonalcoholic fluids', Math.min(Math.max(f.fluidsLiters, 0) / f.fluidsTarget, 1));
    const possible = items.reduce((s, x) => s + x.possible, 0), earned = items.reduce((s, x) => s + x.earned, 0);
    return { percent: possible ? Math.round(earned / possible * 100) : null, earned, possible, items };
  }
  function validEntry(input, today = bangkokDate()) {
    if (!input || typeof input !== 'object' || Array.isArray(input) || !parseDate(input.date) || input.date < '2020-01-01' || input.date > today) return false;
    if (!Number.isFinite(input.score) || input.score < 0 || input.score > 100) return false;
    const max = input.scaleMax === 5 ? 5 : 10;
    if (!input.answers || SUBJECTIVE_KEYS.some(k => !Number.isFinite(input.answers[k]) || input.answers[k] < 0 || input.answers[k] > max)) return false;
    const f = input.foundations || {};
    if (f.anki !== undefined && !['no', 'partial', 'complete'].includes(f.anki)) return false;
    if (f.body !== undefined && !['none', 'recovery', 'workout'].includes(f.body)) return false;
    for (const [key, limits] of Object.entries(FOUNDATION_NUMBERS)) if (f[key] !== undefined && (!Number.isFinite(f[key]) || f[key] < limits[0] || f[key] > limits[1])) return false;
    return ['foodNotes', 'heatExerciseNote'].every(k => f[k] === undefined || (typeof f[k] === 'string' && f[k].length <= 500));
  }
  function validatedEntries(value, today = bangkokDate()) {
    if (!Array.isArray(value)) return [];
    const byDate = new Map();
    value.forEach(entry => { if (validEntry(entry, today) && !byDate.has(entry.date)) byDate.set(entry.date, entry); });
    return [...byDate.values()];
  }
  function aggregate(entries, selectedDate, view) {
    const bounds = period(selectedDate, view);
    const recorded = (Array.isArray(entries) ? entries : []).filter(e => e && parseDate(e.date) && e.date >= bounds.start && e.date <= bounds.end && Number.isFinite(e.score) && e.score >= 0 && e.score <= 100);
    const sum = recorded.reduce((s, e) => s + e.score, 0);
    return { ...bounds, recorded: recorded.length, sum, progress: sum / bounds.days, average: recorded.length ? sum / recorded.length : null };
  }
  const metricDefs = [
    ['energy', 'Energy', e => e.answers.energy, '/10'], ['focus', 'Focus', e => e.answers.focus, '/10'],
    ['stress', 'Stress', e => e.answers.stress, '/10'], ['calm', 'Calm', e => e.answers.calm, '/10'], ['happiness', 'Happiness', e => e.answers.happiness, '/10'],
    ['sleepHours', 'Sleep', e => e.foundations?.sleepHours, 'h'], ['sleepQuality', 'Sleep quality', e => e.foundations?.sleepQuality, '/10'],
    ['proteinGrams', 'Protein', e => e.foundations?.proteinGrams, 'g'], ['balancedDiet', 'Balanced diet', e => e.foundations?.balancedDiet, '/10'],
    ['fluidsLiters', 'Fluids', e => e.foundations?.fluidsLiters, 'L'], ['alcoholCount', 'Alcohol', e => e.foundations?.alcoholCount, ''],
    ['skinComfort', 'Skin comfort', e => e.foundations?.skinComfort, '/10'], ['skinIrritation', 'Skin irritation', e => e.foundations?.skinIrritation, '/10'], ['skinDryness', 'Skin dryness', e => e.foundations?.skinDryness, '/10']
  ];
  function metricSummaries(entries, selectedDate, view) {
    const bounds = period(selectedDate, view), within = validatedEntries(entries).filter(e => e.date >= bounds.start && e.date <= bounds.end && e.scaleMax !== 5 && e.schemaVersion !== 1);
    const out = metricDefs.map(([key, label, get, unit]) => {
      const values = within.map(get).filter(Number.isFinite);
      return { key, label, unit, count: values.length, days: bounds.days, average: values.length ? values.reduce((a, b) => a + b, 0) / values.length : null };
    });
    const categorical = (key, label, allowed) => {
      const values = within.map(e => e.foundations?.[key]).filter(v => allowed.includes(v));
      const counts = Object.fromEntries(allowed.map(v => [v, values.filter(x => x === v).length]));
      out.push({ key, label, count: values.length, days: bounds.days, counts });
    };
    categorical('anki', 'Anki', ['complete', 'partial', 'no']);
    categorical('body', 'Workout / recovery', ['workout', 'recovery', 'none']);
    return out;
  }
  return { VERSION, SUBJECTIVE_KEYS, bangkokDate, parseDate, period, subjectiveScore, foundations, validEntry, validatedEntries, aggregate, metricSummaries };
});
