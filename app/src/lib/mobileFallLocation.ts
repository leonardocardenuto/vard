export type FallCoordinates = { latitude: number; longitude: number; accuracy_m: number; captured_at: string; address?: string };

export function mobileFallCoordinates(payload: Record<string, unknown>): FallCoordinates | null {
  if (payload.source !== 'accelerometer' || !payload.coordinates || typeof payload.coordinates !== 'object') return null;
  const value = payload.coordinates as Partial<FallCoordinates>;
  if (typeof value.latitude !== 'number' || !Number.isFinite(value.latitude) || Math.abs(value.latitude) > 90
    || typeof value.longitude !== 'number' || !Number.isFinite(value.longitude) || Math.abs(value.longitude) > 180
    || typeof value.accuracy_m !== 'number' || !Number.isFinite(value.accuracy_m) || value.accuracy_m < 0
    || typeof value.captured_at !== 'string' || !Number.isFinite(Date.parse(value.captured_at))) return null;
  return value as FallCoordinates;
}

export function mobileFallAddress(payload: Record<string, unknown>): string | null {
  const coordinates = mobileFallCoordinates(payload);
  return typeof coordinates?.address === 'string' && coordinates.address.trim()
    ? coordinates.address.trim() : null;
}
