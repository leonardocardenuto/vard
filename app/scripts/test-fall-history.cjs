const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const Module = require('node:module');
const crypto = require('node:crypto');
const ts = require('typescript');
const { x25519 } = require('@noble/curves/ed25519.js');
const { chacha20poly1305 } = require('@noble/ciphers/chacha.js');
const { hkdf } = require('@noble/hashes/hkdf.js');
const { pbkdf2Async } = require('@noble/hashes/pbkdf2.js');
const { sha256 } = require('@noble/hashes/sha2.js');
const aad = new TextEncoder().encode('vard/fall-event/v2');
const bytes = (n) => new Uint8Array(crypto.randomBytes(n));
const encode = (b) => Buffer.from(b).toString('base64url');

async function main() {
  const privateKey = bytes(32), salt = bytes(16), nonce = bytes(12);
  const recoveryKey = await pbkdf2Async(sha256, new TextEncoder().encode('test-password'), salt, { c: 100000, dkLen: 32 });
  const backup = {
    public_key: encode(x25519.getPublicKey(privateKey)), recovery_salt: encode(salt),
    encrypted_private_key_backup: encode(nonce) + '.' + encode(chacha20poly1305(recoveryKey, nonce, aad).encrypt(privateKey)),
  };
  let stored = encode(bytes(32));
  const filename = path.resolve(__dirname, '../src/lib/fallHistoryCrypto.ts');
  const mod = new Module(filename, module);
  mod.filename = filename;
  mod.paths = module.paths;
  const originalRequire = mod.require.bind(mod);
  mod.require = (name) => {
    if (name === 'expo-crypto') return { getRandomBytesAsync: async (n) => bytes(n) };
    if (name === 'expo-secure-store') return {
      getItemAsync: async () => stored, setItemAsync: async (_key, value) => { stored = value; },
    };
    if (name === './api') return { getEncryptionKey: async () => backup, putEncryptionKey: async () => { throw Error('Must not replace server keys'); }, ApiRequestError: class extends Error {} };
    return originalRequire(name);
  };
  mod._compile(ts.transpileModule(fs.readFileSync(filename, 'utf8'), { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText, filename);
  const contentKey = bytes(32), wrapNonce = bytes(12), ephemeral = bytes(32), payloadNonce = bytes(12);
  const wrappingKey = hkdf(sha256, x25519.getSharedSecret(ephemeral, x25519.getPublicKey(privateKey)), undefined, aad, 32);
  const envelope = { ephemeral_public_key: encode(x25519.getPublicKey(ephemeral)), nonce: encode(wrapNonce), ciphertext: encode(chacha20poly1305(wrappingKey, wrapNonce, aad).encrypt(contentKey)) };
  const video = bytes(3 * 1024 * 1024 + 5);
  const encrypted = Buffer.concat([payloadNonce, chacha20poly1305(contentKey, payloadNonce, aad).encrypt(video)]);
  const restoring = mod.exports.prepareFallHistoryKey('token', 'user', 'test-password');
  const decrypted = await mod.exports.decryptFallClip(encode(encrypted), envelope, 'user');
  await restoring;
  assert.deepEqual(Buffer.from(decrypted), Buffer.from(video));
  assert.equal(stored, Buffer.from(privateKey).toString('base64'));
  stored = null;
  await assert.rejects(mod.exports.decryptFallClip(encode(encrypted), envelope, 'user'), /chave dos vídeos não está/);
  stored = encode(bytes(32));
  await assert.rejects(mod.exports.decryptFallClip(encode(encrypted), envelope, 'user'), /descriptografar/);
  console.log('PASS: restore mismatched key, wait for recovery, decrypt multi-chunk video, report missing/wrong keys');
}
main().catch((error) => { console.error(error); process.exitCode = 1; });
