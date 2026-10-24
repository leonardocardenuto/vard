const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const Module = require('node:module');
const ts = require('typescript');
async function main() {
  const originalAppId = process.env.EXPO_PUBLIC_ONESIGNAL_APP_ID;
  process.env.EXPO_PUBLIC_ONESIGNAL_APP_ID = 'test-app-id';
  try {
    const listeners = {}, appListeners = [], pauses = [], initialized = [], permissions = [];
    const filename = path.resolve(__dirname, '../src/lib/onesignal.ts');
    const mod = new Module(filename, module);
    const sdk = {
      initialize: id => initialized.push(id),
      InAppMessages: { setPaused: value => pauses.push(value), addEventListener: (event, fn) => { listeners[event] = fn; } },
      Notifications: { requestPermission: value => permissions.push(value) },
    };
    mod.require = name => {
      if (name === 'react-native') return {
        Platform: { OS: 'android' }, NativeModules: { OneSignal: {} }, TurboModuleRegistry: { get: () => null },
        AppState: { addEventListener: (event, fn) => { appListeners.push(fn); return { remove() {} }; } },
      };
      if (name === 'react-native-onesignal') return { OneSignal: sdk };
      if (name === './fallAlertQueue') return {};
      throw new Error('Unexpected dependency: ' + name);
    };
    mod._compile(ts.transpileModule(fs.readFileSync(filename, 'utf8'), {
      compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
    }).outputText, filename);
    await Promise.all([mod.exports.initializeOneSignal(), mod.exports.initializeOneSignal()]);
    assert.deepEqual(initialized, ['test-app-id']);
    assert.deepEqual(pauses, [true]);
    assert.deepEqual(permissions, [true]); // Push permission is still requested.
    listeners.willDisplay({});
    listeners.didDisplay({});
    appListeners[0]('background');
    assert.equal(pauses.length, 3);
    appListeners[0]('active');
    assert.deepEqual(pauses, [true, true, true, true]);
    await mod.exports.initializeOneSignal();
    assert.equal(appListeners.length, 1);
    console.log('PASS: campaigns paused on startup, cached display and app resume; push permission and singleton initialization preserved');
  } finally {
    if (originalAppId === undefined) delete process.env.EXPO_PUBLIC_ONESIGNAL_APP_ID;
    else process.env.EXPO_PUBLIC_ONESIGNAL_APP_ID = originalAppId;
  }
}
main().catch(error => { console.error(error); process.exitCode = 1; });
