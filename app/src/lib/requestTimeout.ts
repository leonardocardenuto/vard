export class RequestTimeoutError extends Error {
  constructor() { super('API request timed out'); this.name = 'RequestTimeoutError'; }
}

export async function fetchWithTimeout(url: string, init: RequestInit = {}, milliseconds = 15000): Promise<Response> {
  const controller = new AbortController();
  let timedOut = false;
  const cancel = () => controller.abort();
  if (init.signal?.aborted) cancel();
  init.signal?.addEventListener('abort', cancel);
  const timer = setTimeout(() => { timedOut = true; controller.abort(); }, milliseconds);
  try {
    return await fetch(url, { ...init, signal: controller.signal });
  } catch (error) {
    if (timedOut) throw new RequestTimeoutError();
    throw error;
  } finally {
    clearTimeout(timer);
    init.signal?.removeEventListener('abort', cancel);
  }
}
