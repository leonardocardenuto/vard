import { File, Paths } from 'expo-file-system';

import { FallEventClipResponse, getFallEventClip, getMe } from './api';
import { decryptFallClip } from './fallHistoryCrypto';

const MAX_CACHED_CLIPS = 3;
const currentUserRequests = new Map<string, Promise<string>>();
const clipRequests = new Map<string, Promise<FallEventClipResponse>>();

function currentUserId(accessToken: string) {
  let request = currentUserRequests.get(accessToken);
  if (!request) {
    request = getMe(accessToken)
      .then((user) => user.id)
      .catch((error) => {
        currentUserRequests.delete(accessToken);
        throw error;
      });
    currentUserRequests.set(accessToken, request);
  }
  return request;
}

function encryptedClip(accessToken: string, eventId: string) {
  const key = `${accessToken}:${eventId}`;
  let request = clipRequests.get(key);
  if (!request) {
    request = getFallEventClip(accessToken, eventId).catch((error) => {
      clipRequests.delete(key);
      throw error;
    });
    clipRequests.set(key, request);

    while (clipRequests.size > MAX_CACHED_CLIPS) {
      const oldestKey = clipRequests.keys().next().value as string | undefined;
      if (!oldestKey) break;
      clipRequests.delete(oldestKey);
    }
  }
  return request;
}

export function prefetchFallEventClip(accessToken: string, eventId: string) {
  void Promise.all([currentUserId(accessToken), encryptedClip(accessToken, eventId)]).catch(() => {
    // Opening the clip reports the actionable error. Prefetch remains silent.
  });
}

export async function prepareFallEventClip(accessToken: string, eventId: string) {
  const [userId, clip] = await Promise.all([
    currentUserId(accessToken),
    encryptedClip(accessToken, eventId),
  ]);
  const decryptedClip = await decryptFallClip(clip.encrypted_clip, clip.key_envelope, userId);
  if (!decryptedClip) throw new Error('Trecho indisponível');

  const file = new File(Paths.cache, `vard-fall-${eventId}.mp4`);
  if (file.exists) file.delete();
  file.write(decryptedClip);
  return file.uri;
}

export function removePreparedFallEventClip(uri: string | null) {
  if (!uri) return;
  const file = new File(uri);
  if (file.exists) file.delete();
}
