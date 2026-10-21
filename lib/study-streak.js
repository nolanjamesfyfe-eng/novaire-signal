'use strict';

const FEATURE_START_DATE = '2026-10-21';
const DAY_MS = 86_400_000;
const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/;

function bangkokDate(now = new Date()) {
  return new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Asia/Bangkok', year: 'numeric', month: '2-digit', day: '2-digit'
  }).format(now);
}

function shiftDate(date, amount) {
  const value = new Date(`${date}T00:00:00Z`);
  value.setUTCDate(value.getUTCDate() + amount);
  return value.toISOString().slice(0, 10);
}

function summarize(document = {}, today = bangkokDate()) {
  const startedAt = ISO_DATE.test(document.startedAt || '') ? document.startedAt : FEATURE_START_DATE;
  const clickDates = new Set((Array.isArray(document.clickDates) ? document.clickDates : [])
    .filter(date => ISO_DATE.test(date) && date >= startedAt && date <= today));
  const todayClicked = clickDates.has(today);
  let cursor = todayClicked ? today : shiftDate(today, -1);
  let streak = 0;
  while (clickDates.has(cursor)) {
    streak += 1;
    cursor = shiftDate(cursor, -1);
  }
  const historyStart = [startedAt, shiftDate(today, -6)].sort().at(-1);
  const recentDays = [];
  if (historyStart <= today) {
    const count = Math.round((Date.parse(`${today}T00:00:00Z`) - Date.parse(`${historyStart}T00:00:00Z`)) / DAY_MS);
    for (let offset = 0; offset <= count; offset += 1) {
      const date = shiftDate(historyStart, offset);
      recentDays.push({ date, status: clickDates.has(date) ? 'clicked' : date === today ? 'pending' : 'missed' });
    }
  }
  return {
    startedAt,
    today,
    todayClicked,
    todayStatus: todayClicked ? 'clicked' : 'pending',
    streak,
    recentDays,
  };
}

module.exports = { FEATURE_START_DATE, bangkokDate, shiftDate, summarize };
