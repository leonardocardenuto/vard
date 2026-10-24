const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const Module = require('node:module');
const ts = require('typescript');
function load(file, mocks = {}) {
  const filename = path.resolve(__dirname, '../src/lib', file);
  const mod = new Module(filename, module);
  mod.filename = filename;
  mod.paths = module.paths;
  mod.require = (name) => mocks[name] ?? module.require(name);
  mod._compile(ts.transpileModule(fs.readFileSync(filename, 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
  }).outputText, filename);
  return mod.exports;
}
async function main() {
  const { mobileFallCoordinates, mobileFallAddress } = load('mobileFallLocation.ts');
  const coordinates = { latitude: 0, longitude: -46.6333, accuracy_m: 0, captured_at: '2026-10-23T12:00:00Z' };
  assert.deepEqual(mobileFallCoordinates({ source: 'accelerometer', coordinates }), coordinates);
  for (const value of [undefined, null, {}, { ...coordinates, latitude: 91 },
    { ...coordinates, longitude: Infinity }, { ...coordinates, accuracy_m: -1 },
    { ...coordinates, captured_at: 'invalid' }]) {
    assert.equal(mobileFallCoordinates({ source: 'accelerometer', coordinates: value }), null);
  }
  assert.equal(mobileFallCoordinates({ source: 'camera', coordinates }), null);
  assert.equal(mobileFallAddress({ source: 'accelerometer', coordinates: { ...coordinates, address: '  Praça da Sé, São Paulo - SP  ' } }), 'Praça da Sé, São Paulo - SP');
  assert.equal(mobileFallAddress({ source: 'accelerometer', coordinates }), null);
  assert.equal(mobileFallAddress({ source: 'accelerometer', coordinates: { ...coordinates, address: {} } }), null);
  assert.equal(mobileFallAddress({ source: 'camera', coordinates: { ...coordinates, address: 'Rua' } }), null);
  const started = [], requested = [];
  const api = { mobileMonitorBaseUrl: () => 'http://local', registerMobileMonitor: async () => ({ device_token: 'device' }) };
  const monitor = load('mobileFallMonitor.ts', {
    './api': api,
    'react-native': {
      Platform: { OS: 'android', Version: 35 },
      NativeModules: { VardFallMonitor: { status: async () => ({ sensorAvailable: true }), start: async (...args) => started.push(args) } },
      PermissionsAndroid: {
        PERMISSIONS: { POST_NOTIFICATIONS: 'notifications', ACCESS_COARSE_LOCATION: 'coarse', ACCESS_FINE_LOCATION: 'fine' },
        RESULTS: { GRANTED: 'granted' }, request: async () => 'granted',
        requestMultiple: async (permissions) => { requested.push(permissions); return { coarse: 'denied', fine: 'denied' }; },
      },
    },
  });
  await monitor.startMobileFallMonitor('access', 'workspace');
  assert.deepEqual(requested, [['coarse', 'fine']]);
  assert.deepEqual(started, [['http://local', 'device', 'workspace']]);
  console.log('PASS: mobile-only coordinates, valid zero, invalid/legacy payloads, permission denial preserves monitoring');
}
main().catch((error) => { console.error(error); process.exitCode = 1; });
