import assert from 'node:assert/strict';
import { test } from 'node:test';
import { fallOccurrenceTarget, newFallNotices, pushFallId } from '../src/lib/fallAlertQueue.ts';

test('new falls and confrontations are queued once across push and polling', () => {
  const start = Date.parse('2026-10-20T12:00:00Z');
  const seen = new Set<string>();
  const current = { id: 'fall', notification_type: 'fall_detected', created_at: '2026-10-20T12:00:02Z' };
  const fight = { ...current, id: 'fight', notification_type: 'confrontation_detected' };
  const items = [current, { ...current, id: 'old', created_at: '2026-10-19T12:00:00Z' },
    fight, { ...current, id: 'other', notification_type: 'other' }, current];
  assert.deepEqual(newFallNotices(items, seen, start), [current, fight]);
  assert.deepEqual(newFallNotices([current], seen, start), []);
  assert.deepEqual(newFallNotices([fight], seen, start), []);
});

test('distinct falls remain in chronological order and sessions do not share seen IDs', () => {
  const older = { id: 'a', notification_type: 'fall_detected', created_at: '2026-10-20T12:00:01Z' };
  const newer = { ...older, id: 'b', created_at: '2026-10-20T12:00:02Z' };
  assert.deepEqual(newFallNotices([newer, older], new Set(), 0), [older, newer]);
  assert.deepEqual(newFallNotices([older], new Set(), 0), [older]);
});

test('push navigation accepts falls and confrontations and requires a notification ID', () => {
  assert.equal(pushFallId({ notification_type: 'fall_detected', notification_id: 'fall-id' }), 'fall-id');
  assert.equal(pushFallId({ notification_type: 'confrontation_detected', notification_id: 'fight-id' }), 'fight-id');
  assert.equal(pushFallId({ notification_type: 'other', notification_id: 'other-id' }), null);
  assert.equal(pushFallId({ notification_type: 'fall_detected' }), null);
  assert.equal(pushFallId(null), null);
});

test('phone falls open only the workspace associated with the notification', () => {
  assert.deepEqual(fallOccurrenceTarget({ workspace_id: 'casa-vard', camera_id: null,
    payload: { source: 'accelerometer' } }), {
    screen: 'WorkspaceOccurrences', params: { workspaceId: 'casa-vard' },
  });
  assert.deepEqual(fallOccurrenceTarget({ workspace_id: 'other-house', camera_id: null,
    payload: { source: 'accelerometer' } })?.params, { workspaceId: 'other-house' });
});

test('camera falls retain their camera scope', () => {
  assert.deepEqual(fallOccurrenceTarget({ workspace_id: 'casa-vard', camera_id: 'maua',
    payload: { camera_name: 'Maua' } }), {
    screen: 'CameraOccurrences', params: { workspaceId: 'casa-vard', cameraId: 'maua', cameraName: 'Maua' },
  });
});
