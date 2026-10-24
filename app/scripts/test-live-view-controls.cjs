const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const ts = require('typescript');
const source = fs.readFileSync(require('node:path').join(__dirname, '../src/views/settings/pages/CameraLiveViewScreen.tsx'), 'utf8');
const ast = ts.createSourceFile('live.tsx', source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
let injected;
const views = [];
function visit(node) {
  if (ts.isVariableDeclaration(node) && node.name.getText(ast) === 'CAMERA_WEBVIEW_INJECTED_JS') injected = node.initializer.text;
  if (ts.isJsxSelfClosingElement(node) && node.tagName.getText(ast) === 'VideoView') views.push(node.getText(ast));
  ts.forEachChild(node, visit);
}
visit(ast);
assert(views.some(view => view.includes('player={player}') && view.includes('nativeControls={false}')));
assert(views.some(view => view.includes('player={clipPlayer}') && !view.includes('nativeControls={false}') && view.includes('nativeControls')));
const video = { controls: true, readyState: 2, removeAttribute(name) { this.removed = name; } };
const callbacks = [];
const messages = [];
vm.runInNewContext(injected, {
  window: { ReactNativeWebView: { postMessage: value => messages.push(JSON.parse(value)) }, addEventListener() {} },
  document: { getElementById: () => ({}), querySelectorAll: type => type === 'video' ? [video] : [], addEventListener() {} },
  setInterval: callback => callbacks.push(callback), setTimeout() {}, clearInterval() {}, clearTimeout() {},
});
callbacks.forEach(callback => callback());
assert.equal(video.controls, false);
assert.equal(video.removed, 'controls');
assert.deepEqual(messages, [{ type: 'connected' }]);
console.log('PASS: live HLS and WebView hide controls; recorded clips retain controls; stream readiness preserved');
