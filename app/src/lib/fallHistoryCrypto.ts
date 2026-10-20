import * as Crypto from 'expo-crypto';
import * as SecureStore from 'expo-secure-store';
import { chacha20poly1305 } from '@noble/ciphers/chacha.js';
import { x25519 } from '@noble/curves/ed25519.js';
import { hkdf } from '@noble/hashes/hkdf.js';
import { pbkdf2Async } from '@noble/hashes/pbkdf2.js';
import { sha256 } from '@noble/hashes/sha2.js';

import { ApiRequestError, getEncryptionKey, putEncryptionKey } from './api';

const AAD = new TextEncoder().encode('vard/fall-event/v2');
const storageKey = (userId: string) => `vard.fall-history.private-key.${userId}`;
const pendingKeys = new Map<string, Promise<void>>();

export function prepareFallHistoryKey(token: string, userId: string, password: string) {
  const pending = pendingKeys.get(userId);
  if (pending) return pending;
  const request = restoreFallHistoryKey(token, userId, password);
  pendingKeys.set(userId, request);
  void request.finally(() => {
    if (pendingKeys.get(userId) === request) pendingKeys.delete(userId);
  }).catch(() => {});
  return request;
}

async function restoreFallHistoryKey(token: string, userId: string, password: string) {
  const savedPrivateKey = await SecureStore.getItemAsync(storageKey(userId));

  if (savedPrivateKey) {
    try {
      const backup = await getEncryptionKey(token);
      const publicKey = x25519.getPublicKey(decode(savedPrivateKey));
      const expected = decode(backup.public_key);
      if (publicKey.length !== expected.length || publicKey.some((byte, index) => byte !== expected[index])) {
        const restored = await decryptBackup(backup.encrypted_private_key_backup, backup.recovery_salt, password);
        await SecureStore.setItemAsync(storageKey(userId), encode(restored), { keychainAccessible: SecureStore.WHEN_UNLOCKED_THIS_DEVICE_ONLY });
      }
      return;
    } catch (error) {
      if (!isNotFound(error)) throw error;
      await uploadPrivateKey(token, decode(savedPrivateKey), password);
      return;
    }
  }

  try {
    const backup = await getEncryptionKey(token);
    const privateKey = await decryptBackup(backup.encrypted_private_key_backup, backup.recovery_salt, password);
    await SecureStore.setItemAsync(storageKey(userId), encode(privateKey), { keychainAccessible: SecureStore.WHEN_UNLOCKED_THIS_DEVICE_ONLY });
  } catch (error) {
    if (!isNotFound(error)) throw error;
    const privateKey = await Crypto.getRandomBytesAsync(32);
    await uploadPrivateKey(token, privateKey, password);
    await SecureStore.setItemAsync(storageKey(userId), encode(privateKey), { keychainAccessible: SecureStore.WHEN_UNLOCKED_THIS_DEVICE_ONLY });
  }
}

function isNotFound(error: unknown) {
  // Some native runtimes do not preserve Error subclasses across async
  // boundaries, so prefer the response shape over instanceof here.
  return (
    error instanceof ApiRequestError
    || (typeof error === 'object' && error !== null && 'status' in error)
  ) && (error as { status?: unknown }).status === 404;
}

async function uploadPrivateKey(token: string, privateKey: Uint8Array, password: string) {
  const salt = await Crypto.getRandomBytesAsync(16);
  await putEncryptionKey(token, {
    public_key: encode(x25519.getPublicKey(privateKey)),
    encrypted_private_key_backup: await encryptBackup(privateKey, salt, password),
    recovery_salt: encode(salt),
  });
}

export async function decryptFallOccurredAt(encryptedPayload: string, envelope: Record<string, string>, userId: string) {
  const decrypted = await decryptFallPayload(encryptedPayload, envelope, userId);
  return decrypted ? new TextDecoder().decode(decrypted) : null;
}

export async function decryptFallClip(encryptedClip: string, envelope: Record<string, string>, userId: string) {
  try {
    await pendingKeys.get(userId);
  } catch {
    throw new Error('Não foi possível recuperar a chave dos vídeos. Saia e entre novamente com sua senha.');
  }
  return decryptFallPayload(encryptedClip, envelope, userId, true);
}

async function decryptFallPayload(encryptedPayload: string, envelope: Record<string, string>, userId: string, reportError = false) {
  const encodedPrivateKey = await SecureStore.getItemAsync(storageKey(userId));
  if (!encodedPrivateKey) {
    if (reportError) throw new Error('A chave dos vídeos não está neste celular. Saia e entre novamente com sua senha.');
    return null;
  }
  if (!envelope.ephemeral_public_key || !envelope.nonce || !envelope.ciphertext) {
    if (reportError) throw new Error('Este vídeo não possui uma chave de acesso para sua conta.');
    return null;
  }
  try {
    const sharedSecret = x25519.getSharedSecret(decode(encodedPrivateKey), decode(envelope.ephemeral_public_key));
    const wrappingKey = hkdf(sha256, sharedSecret, undefined, AAD, 32);
    const contentKey = chacha20poly1305(wrappingKey, decode(envelope.nonce), AAD).decrypt(decode(envelope.ciphertext));
    const payload = decode(encryptedPayload);
    return chacha20poly1305(contentKey, payload.subarray(0, 12), AAD).decrypt(payload.subarray(12));
  } catch {
    if (reportError) throw new Error('Não foi possível descriptografar este vídeo. Saia e entre novamente com sua senha para recuperar a chave.');
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
  const result = new Uint8Array(padded.length / 4 * 3 - (padded.endsWith('==') ? 2 : padded.endsWith('=') ? 1 : 0));
  let offset = 0;
  for (let start = 0; start < padded.length; start += 32768) {
    const chunk = atob(padded.slice(start, start + 32768));
    for (let index = 0; index < chunk.length; index++) result[offset++] = chunk.charCodeAt(index);
  }
  return result;
}
