import { useEffect, useRef } from 'react';

import { NotificationResponse, buildWebSocketUrl } from '../lib/api';

type Options = {
  accessToken: string;
  workspaceIds: string[];
  onNotification: (notification: NotificationResponse) => void;
  enabled?: boolean;
};

export function useRealtimeNotifications({
  accessToken,
  workspaceIds,
  onNotification,
  enabled = true,
}: Options): void {
  const onNotificationRef = useRef(onNotification);
  useEffect(() => {
    onNotificationRef.current = onNotification;
  });

  const workspaceIdsKey = workspaceIds.join(',');

  useEffect(() => {
    if (!enabled || !accessToken || !workspaceIdsKey) return;

    const seenIds = new Set<string>();
    let ws: WebSocket | null = null;
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
    let active = true;
    let backoff = 1000;

    function connect() {
      if (!active) return;

      const url = buildWebSocketUrl('/notifications/stream');
      const params = new URLSearchParams({
        token: accessToken,
        workspace_ids: workspaceIdsKey,
      });

      ws = new WebSocket(`${url}?${params.toString()}`);

      ws.onopen = () => {
        backoff = 1000;
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data as string) as {
            event: string;
            notification: NotificationResponse;
          };
          if (data.event !== 'notification.created') return;
          const n = data.notification;
          if (!n?.id || seenIds.has(n.id)) return;
          seenIds.add(n.id);
          onNotificationRef.current(n);
        } catch {
          // ignore invalid messages
        }
      };

      ws.onclose = (event) => {
        if (!active) return;
        // Do not reconnect on auth/access errors
        if (event.code === 4001 || event.code === 4003) return;
        backoff = Math.min(backoff * 2, 30_000);
        reconnectTimer = setTimeout(connect, backoff);
      };
    }

    connect();

    return () => {
      active = false;
      if (reconnectTimer) clearTimeout(reconnectTimer);
      ws?.close();
    };
  }, [enabled, accessToken, workspaceIdsKey]);
}
