import assert from 'node:assert/strict';
import { test } from 'node:test';
import { fetchWithTimeout, RequestTimeoutError } from '../src/lib/requestTimeout.ts';

test('a pending request is aborted at its deadline', async () => {
  const original = globalThis.fetch;
  let receivedSignal: AbortSignal | null | undefined;
  globalThis.fetch = async (_url, init) => new Promise((_resolve, reject) => {
    receivedSignal = init?.signal;
    receivedSignal?.addEventListener('abort', () => reject(new Error('aborted')));
  });
  try {
    await assert.rejects(fetchWithTimeout('http://api.test', {}, 10), RequestTimeoutError);
    assert.equal(receivedSignal?.aborted, true);
  } finally { globalThis.fetch = original; }
});

test('a successful response is returned and external cancellation is preserved', async () => {
  const original = globalThis.fetch;
  const response = new Response('{}', { status: 200 });
  globalThis.fetch = async () => response;
  try { assert.equal(await fetchWithTimeout('http://api.test'), response); }
  finally { globalThis.fetch = original; }
  const controller = new AbortController();
  globalThis.fetch = async (_url, init) => new Promise((_resolve, reject) => {
    init?.signal?.addEventListener('abort', () => reject(new Error('cancelled')));
  });
  try {
    const pending = fetchWithTimeout('http://api.test', { signal: controller.signal });
    controller.abort();
    await assert.rejects(pending, /cancelled/);
  } finally { globalThis.fetch = original; }
});
