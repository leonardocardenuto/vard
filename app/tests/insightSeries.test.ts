import assert from 'node:assert/strict';
import { test } from 'node:test';
import { buildIncidentSeries } from '../src/lib/insightSeries.ts';

test('seven calendar days include today, zeroes and exact day boundaries', () => {
  const start = new Date(2026, 9, 13).getTime();
  const end = new Date(2026, 9, 19, 14).getTime();
  const series = buildIncidentSeries([
    { created_at: new Date(2026, 9, 13).toISOString() },
    { created_at: new Date(2026, 9, 18, 23, 59, 59).toISOString() },
    { created_at: new Date(2026, 9, 19).toISOString() },
    { created_at: new Date(2026, 9, 12, 23, 59, 59).toISOString() },
    { created_at: new Date(2026, 9, 19, 15).toISOString() },
    { created_at: 'invalid' },
  ], start, end);
  assert.equal(series.length, 7);
  assert.deepEqual(series.map((day) => day.label), ['13/10', '14/10', '15/10', '16/10', '17/10', '18/10', '19/10']);
  assert.deepEqual(series.map((day) => day.value), [1, 0, 0, 0, 0, 1, 1]);
});

test('longer filter periods retain a daily count rather than eight arbitrary buckets', () => {
  const start = new Date(2026, 8, 20).getTime();
  const end = new Date(2026, 9, 19, 14).getTime();
  const series = buildIncidentSeries([], start, end);
  assert.equal(series.length, 30);
  assert.ok(series.every((day) => day.value === 0));
});

test('calendar-day stepping handles a daylight-saving transition', () => {
  const previous = process.env.TZ;
  process.env.TZ = 'America/New_York';
  try {
    const series = buildIncidentSeries([], new Date(2026, 2, 5).getTime(), new Date(2026, 2, 11, 12).getTime());
    assert.equal(series.length, 7);
    assert.equal(new Set(series.map((day) => day.label)).size, 7);
  } finally {
    if (previous === undefined) delete process.env.TZ;
    else process.env.TZ = previous;
  }
});
