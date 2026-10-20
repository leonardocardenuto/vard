import { Feather } from '@expo/vector-icons';
import { useEffect, useRef, useState } from 'react';
import { AppState, Modal, Pressable, StyleSheet, Text, View } from 'react-native';
import { getNotification, listNotifications, listWorkspaces, NotificationResponse } from '../lib/api';
import { newFallNotices } from '../lib/fallAlertQueue';
import { subscribeToFallPush } from '../lib/onesignal';

export function GlobalFallAlert({ accessToken, onOpen }: {
  accessToken: string; onOpen: (notification: NotificationResponse) => void;
}) {
  const [queue, setQueue] = useState<NotificationResponse[]>([]);
  const onOpenRef = useRef(onOpen);
  onOpenRef.current = onOpen;
  useEffect(() => {
    if (!accessToken) return;
    let active = true;
    let checking = false;
    const since = Date.now();
    const seen = new Set<string>();
    setQueue([]);
    const receive = (items: NotificationResponse[]) => {
      if (!active) return;
      const fresh = newFallNotices(items, seen, since);
      if (fresh.length) setQueue((current) => [...current, ...fresh]);
    };
    const check = async () => {
      if (!active || checking || AppState.currentState !== 'active') return;
      checking = true;
      try {
        const workspaces = await listWorkspaces(accessToken);
        const results = await Promise.allSettled(workspaces.map((w) => listNotifications(accessToken, w.id)));
        receive(results.flatMap((result) => result.status === 'fulfilled' ? result.value : []));
      } catch { /* A failed poll is retried; keep the current alert visible. */ }
      finally { checking = false; }
    };
    let unsubscribe = () => {};
    void subscribeToFallPush((id, clicked) => {
      void getNotification(accessToken, id).then((notification) => {
        if (!active || notification.notification_type !== 'fall_detected') return;
        if (clicked) {
          seen.add(id);
          setQueue((current) => current.filter((item) => item.id !== id));
          onOpenRef.current(notification);
        } else receive([notification]);
      }).catch(() => void check());
    }).then((cleanup) => { if (active) unsubscribe = cleanup; else cleanup(); }).catch(() => {});
    void check();
    const timer = setInterval(() => void check(), 4000);
    const listener = AppState.addEventListener('change', (state) => { if (state === 'active') void check(); });
    return () => { active = false; clearInterval(timer); listener.remove(); unsubscribe(); };
  }, [accessToken]);
  const notification = queue[0];
  const dismiss = () => setQueue((current) => current.slice(1));
  return <Modal transparent animationType="fade" visible={Boolean(notification)} onRequestClose={dismiss}>
    <View style={styles.backdrop}>
      <View accessibilityViewIsModal style={styles.card}>
        <Feather name="alert-triangle" size={42} color="#FFF" />
        <Text accessibilityRole="alert" accessibilityLiveRegion="assertive" style={styles.title}>Queda detectada</Text>
        <Text style={styles.body}>{notification?.body}</Text>
        <Text style={styles.hint}>Verifique a ocorrência e se a pessoa precisa de ajuda.</Text>
        <Pressable accessibilityRole="button" style={styles.primary} onPress={() => {
          if (notification) { dismiss(); onOpenRef.current(notification); }
        }}><Text style={styles.primaryText}>{notification?.payload.source === 'accelerometer'
          ? 'Ver ocorrências do workspace' : notification?.camera_id ? 'Ver ocorrências da câmera' : 'Ver ocorrência'}</Text></Pressable>
        <Pressable accessibilityRole="button" style={styles.secondary} onPress={dismiss}>
          <Text style={styles.secondaryText}>Fechar aviso</Text>
        </Pressable>
      </View>
    </View>
  </Modal>;
}

const styles = StyleSheet.create({
  backdrop: { flex: 1, backgroundColor: 'rgba(16,24,40,0.65)', justifyContent: 'center', padding: 24 },
  card: { width: '100%', maxWidth: 480, alignSelf: 'center', borderRadius: 22, padding: 26, backgroundColor: '#B42318', alignItems: 'center' },
  title: { color: '#FFF', fontFamily: 'Poppins-Bold', fontSize: 24, marginTop: 14, textAlign: 'center' },
  body: { color: '#FFF', fontFamily: 'Poppins-Medium', fontSize: 15, lineHeight: 23, textAlign: 'center', marginTop: 12 },
  hint: { color: '#FEE4E2', fontFamily: 'Poppins-Regular', fontSize: 13, textAlign: 'center', marginTop: 12 },
  primary: { minHeight: 48, width: '100%', justifyContent: 'center', alignItems: 'center', backgroundColor: '#FFF', borderRadius: 12, marginTop: 24, padding: 12 },
  primaryText: { color: '#B42318', fontFamily: 'Poppins-SemiBold', fontSize: 15, textAlign: 'center' },
  secondary: { minHeight: 48, justifyContent: 'center', padding: 12, marginTop: 6 },
  secondaryText: { color: '#FFF', fontFamily: 'Poppins-Medium', fontSize: 14 },
});
