import assert from 'node:assert/strict';
import { test } from 'node:test';
import vm from 'node:vm';
import { buildMjpegViewerHtml, isMjpegStreamUrl, parseCameraStreamMessage } from '../src/lib/cameraStream.ts';

function viewer() {
  const messages: string[] = [];
  const intervals: Array<() => void> = [];
  const timeouts: Array<() => void> = [];
  const image = { naturalWidth: 0, src: '', onload: null as (() => void) | null, onerror: null as (() => void) | null };
  const html = buildMjpegViewerHtml('http://camera.test:8080/video');
  const script = html.match(/<script>([\s\S]*)<\/script>/)![1];
  vm.runInNewContext(script, {
    document: { getElementById: () => image, documentElement: { setAttribute() {} } },
    window: { ReactNativeWebView: { postMessage: (data: string) => messages.push(JSON.parse(data).type) }, addEventListener() {} },
    setInterval: (fn: () => void) => intervals.push(fn), clearInterval() {},
    setTimeout: (fn: () => void) => timeouts.push(fn), clearTimeout() {},
  });
  return { image, messages, poll: () => intervals.forEach((fn) => fn()), timeout: () => timeouts.forEach((fn) => fn()) };
}

test('MJPEG URLs are distinguished from HTML pages and ordinary videos', () => {
  assert.equal(isMjpegStreamUrl('http://192.168.15.131:8080/video'), true);
  assert.equal(isMjpegStreamUrl('https://camera.test/live.mjpg?token=example'), true);
  assert.equal(isMjpegStreamUrl('http://camera.test/browserfs.html'), false);
  assert.equal(isMjpegStreamUrl('https://camera.test/live.mp4'), false);
  assert.equal(isMjpegStreamUrl('invalid'), false);
});

test('connected waits for a decoded frame, without waiting for the stream to end', () => {
  const state = viewer();
  state.poll();
  assert.deepEqual(state.messages, []);
  assert.equal(state.image.src, 'http://camera.test:8080/video');
  state.image.naturalWidth = 1920;
  state.poll();
  state.poll();
  assert.deepEqual(state.messages, ['connected']);
});

test('a disconnected stream is not declared connected because its last frame is cached', () => {
  const state = viewer();
  state.image.naturalWidth = 1920;
  state.poll();
  state.image.onerror!();
  state.poll();
  assert.deepEqual(state.messages, ['connected', 'error']);
});

test('a camera that never returns an image reports an error instead of spinning forever', () => {
  const state = viewer();
  state.timeout();
  state.poll();
  assert.deepEqual(state.messages, ['error']);
});

test('viewer URLs cannot inject scripts and must use HTTP', () => {
  const html = buildMjpegViewerHtml('http://camera.test/video?x=</script><script>danger</script>');
  assert.equal((html.match(/<script>/g) ?? []).length, 1);
  assert.throws(() => buildMjpegViewerHtml('javascript:alert(1)'), /HTTP/);
});

test('only recognized viewer status messages affect connection state', () => {
  assert.equal(parseCameraStreamMessage('{"type":"connected"}'), 'connected');
  assert.equal(parseCameraStreamMessage('{"type":"error"}'), 'error');
  assert.equal(parseCameraStreamMessage('{"type":"other"}'), null);
  assert.equal(parseCameraStreamMessage('not json'), null);
});
