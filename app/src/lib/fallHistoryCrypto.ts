import * as Crypto from 'expo-crypto';
import * as SecureStore from 'expo-secure-store';
import { chacha20poly1305 } from '@noble/ciphers/chacha.js';
import { x25519 } from '@noble/curves/ed25519.js';
import { hkdf } from '@noble/hashes/hkdf.js';
import { pbkdf2Async } from '@noble/hashes/pbkdf2.js';
import { sha256 } from '@noble/hashes/sha2.js';

import { getEncryptionKey, putEncryptionKey } from './api';

const AAD = new TextEncoder().encode('vard/fall-event/v2');
const storageKey = (userId: string) => `vard.fall-history.private-key.${userId}`;

export async function prepareFallHistoryKey(token: string, userId: string, password: string) {
  const savedPrivateKey = await SecureStore.getItemAsync(storageKey(userId));
  if (savedPrivateKey) return;

  try {
    const backup = await getEncryptionKey(token);
    const privateKey = await decryptBackup(backup.encrypted_private_key_backup, backup.recovery_salt, password);
    await SecureStore.setItemAsync(storageKey(userId), encode(privateKey), { keychainAccessible: SecureStore.WHEN_UNLOCKED_THIS_DEVICE_ONLY });
  } catch (error) {
    if (!(error instanceof Error) || !error.message.toLowerCase().includes('not found')) throw error;
    const privateKey = await Crypto.getRandomBytesAsync(32);
    const salt = await Crypto.getRandomBytesAsync(16);
    const publicKey = x25519.getPublicKey(privateKey);
    await putEncryptionKey(token, {
      public_key: encode(publicKey),
      encrypted_private_key_backup: await encryptBackup(privateKey, salt, password),
      recovery_salt: encode(salt),
    });
    await SecureStore.setItemAsync(storageKey(userId), encode(privateKey), { keychainAccessible: SecureStore.WHEN_UNLOCKED_THIS_DEVICE_ONLY });
  }
}

export async function decryptFallOccurredAt(encryptedPayload: string, envelope: Record<string, string>, userId: string) {
  const decrypted = await decryptFallPayload(encryptedPayload, envelope, userId);
  return decrypted ? new TextDecoder().decode(decrypted) : null;
}

export async function decryptFallClip(encryptedClip: string, envelope: Record<string, string>, userId: string) {
  return decryptFallPayload(encryptedClip, envelope, userId);
}

async function decryptFallPayload(encryptedPayload: string, envelope: Record<string, string>, userId: string) {
  const encodedPrivateKey = await SecureStore.getItemAsync(storageKey(userId));
  if (!encodedPrivateKey || !envelope.ephemeral_public_key || !envelope.nonce || !envelope.ciphertext) return null;
  try {
    const sharedSecret = x25519.getSharedSecret(decode(encodedPrivateKey), decode(envelope.ephemeral_public_key));
    const wrappingKey = hkdf(sha256, sharedSecret, undefined, AAD, 32);
    const contentKey = chacha20poly1305(wrappingKey, decode(envelope.nonce), AAD).decrypt(decode(envelope.ciphertext));
    const payload = decode(encryptedPayload);
    return chacha20poly1305(contentKey, payload.slice(0, 12), AAD).decrypt(payload.slice(12));
  } catch {
    return null;
  }
}

async function encryptBackup(privateKey: Uint8Array, salt: Uint8Array, password: string) {
  const nonce = await Crypto.getRandomBytesAsync(12);
  return encode(nonce) + '.' + encode(chacha20poly1305(await recoveryKey(password, salt), nonce, AAD).encrypt(privateKey));
}

async function decryptBackup(value: string, encodedSalt: string, password: string) {
  const [encodedNonce, encodedCiphertext] = value.split('.');
  if (!encodedNonce || !encodedCiphertext) throw new Error('Cópia de recuperação inválida.');
  return chacha20poly1305(await recoveryKey(password, decode(encodedSalt)), decode(encodedNonce), AAD).decrypt(decode(encodedCiphertext));
}

async function recoveryKey(password: string, salt: Uint8Array) {
  return pbkdf2Async(sha256, new TextEncoder().encode(password), salt, { c: 100_000, dkLen: 32, asyncTick: 8 });
}

function encode(value: Uint8Array) {
  return btoa(String.fromCharCode(...value));
}

function decode(value: string) {
  // The API uses URL-safe Base64 so encrypted values can travel in JSON without
  // escaping. `atob` only accepts the standard alphabet on Android.
  const normalized = value.replace(/-/g, '+').replace(/_/g, '/');
  const padded = normalized.padEnd(normalized.length + ((4 - (normalized.length % 4)) % 4), '=');
  return Uint8Array.from(atob(padded), (char) => char.charCodeAt(0));
}
