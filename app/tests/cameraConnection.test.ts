import assert from 'node:assert/strict';
import { test } from 'node:test';
import { normalizeLocalCameraUrl } from '../src/lib/cameraConnection.ts';

test('an IP with a port never gets a second port appended', () => {
  assert.equal(normalizeLocalCameraUrl('192.168.15.131:8080'), 'http://192.168.15.131:8080/video');
  assert.equal(normalizeLocalCameraUrl('192.168.15.131:8090'), 'http://192.168.15.131:8090/video');
  assert.equal(normalizeLocalCameraUrl('192.168.15.131:80'), 'http://192.168.15.131/video');
});

test('an IP alone uses the IP Webcam port and a stream rather than an HTML page', () => {
  assert.equal(normalizeLocalCameraUrl('192.168.15.131'), 'http://192.168.15.131:8080/video');
  assert.equal(normalizeLocalCameraUrl('http://192.168.15.131:8080/browserfs.html'), 'http://192.168.15.131:8080/video');
});

test('full URLs retain their protocol, port, custom stream and query', () => {
  assert.equal(normalizeLocalCameraUrl('https://camera.test:8443/stream?channel=2'), 'https://camera.test:8443/stream?channel=2');
  assert.equal(normalizeLocalCameraUrl('http://camera.test/'), 'http://camera.test/video');
});

test('invalid input gives a useful validation message', () => {
  assert.throws(() => normalizeLocalCameraUrl(''), /Informe/);
  assert.throws(() => normalizeLocalCameraUrl('192.168.15.131:8080:8080'), /válido/);
  assert.throws(() => normalizeLocalCameraUrl('rtsp://camera.test/live'), /HTTP/);
});
