'use strict';

const FEATURE_START_DATE = '2026-10-21';
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
  let missedDays = 0;
  if (!todayClicked) {
    cursor = shiftDate(today, -1);
    while (cursor >= startedAt && !clickDates.has(cursor)) {
      missedDays += 1;
      cursor = shiftDate(cursor, -1);
    }
  }
  return {
    startedAt,
    today,
    todayClicked,
    todayStatus: todayClicked ? 'clicked' : 'pending',
    streak,
    missedDays,
  };
}

module.exports = { FEATURE_START_DATE, bangkokDate, shiftDate, summarize };
