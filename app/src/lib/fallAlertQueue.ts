export function isDetectionNotice(type: string): boolean {
  return type === 'fall_detected' || type === 'confrontation_detected';
}

export type FallNotice = { id: string; notification_type: string; created_at: string };

export function newFallNotices<T extends FallNotice>(items: T[], seen: Set<string>, since: number): T[] {
  return items.filter((item) => isDetectionNotice(item.notification_type)
    && Date.parse(item.created_at) >= since && !seen.has(item.id))
    .sort((a, b) => Date.parse(a.created_at) - Date.parse(b.created_at))
    .filter((item) => { if (seen.has(item.id)) return false; seen.add(item.id); return true; });
}

export function pushFallId(data: unknown): string | null {
  if (!data || typeof data !== 'object') return null;
  const value = data as Record<string, unknown>;
  return typeof value.notification_type === 'string' && isDetectionNotice(value.notification_type) && typeof value.notification_id === 'string'
    ? value.notification_id : null;
}

export function fallOccurrenceTarget(notification: {
  workspace_id: string; camera_id: string | null; payload: Record<string, unknown>;
}) {
  if (notification.payload.source === 'accelerometer') {
    return { screen: 'WorkspaceOccurrences' as const, params: { workspaceId: notification.workspace_id } };
  }
  if (notification.camera_id) {
    return { screen: 'CameraOccurrences' as const, params: {
      workspaceId: notification.workspace_id, cameraId: notification.camera_id,
      cameraName: typeof notification.payload.camera_name === 'string' ? notification.payload.camera_name : 'Câmera',
    } };
  }
  return null;
}
