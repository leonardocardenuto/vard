import * as Crypto from 'expo-crypto';
import * as SecureStore from 'expo-secure-store';
import { Platform } from 'react-native';
import { acknowledgePush, registerPushDevice, revokePushDevices, updateMyOneSignalSubscription } from './api';
import { identifyOneSignalUser, initializeOneSignal, listenOneSignalNotifications } from './onesignal';
import { loadToken } from './sessionToken';

type NotificationsModule = typeof import('expo-notifications');
const mode = process.env.EXPO_PUBLIC_PUSH_MODE ?? 'onesignal';
let initialization: Promise<void> | null = null;
let installation: Promise<string> | null = null;
let notifications: NotificationsModule | null = null;

export function getPushInstallationId() {
  if (!installation) installation = (async () => {
    const key = 'vard_push_installation';
    let value = await SecureStore.getItemAsync(key);
    if (!value) { value = Crypto.randomUUID(); await SecureStore.setItemAsync(key, value); }
    return value;
  })();
  return installation;
}

async function received(data: unknown, source: 'foreground' | 'tap') {
  if (!data || typeof data !== 'object') return;
  const id = (data as Record<string, unknown>).push_delivery_id;
  if (typeof id !== 'string' || !/^[0-9a-f-]{36}$/i.test(id)) return;
  try {
    const token = await loadToken();
    if (token) await acknowledgePush(token, id, source);
  } catch { /* On tap/open we can acknowledge again. A provider ACK is not receipt. */ }
}

export function initializePushNotifications() {
  if (initialization) return initialization;
  initialization = (async () => {
    if (Platform.OS !== 'android') { await initializeOneSignal(); return; }
    if (mode !== 'fcm') {
      await initializeOneSignal();
      await listenOneSignalNotifications((data, source) => void received(data, source));
    }
    if (mode !== 'onesignal') {
      try {
        notifications = require('expo-notifications') as NotificationsModule;
        notifications.setNotificationHandler({ handleNotification: async () => ({
          shouldShowBanner: true, shouldShowList: true, shouldPlaySound: true, shouldSetBadge: false,
        }) });
        await notifications.setNotificationChannelAsync('vard-alerts', {
          name: 'Alertas VARD', importance: notifications.AndroidImportance.HIGH,
          sound: 'default', vibrationPattern: [0, 250, 250, 250],
        });
        notifications.addNotificationReceivedListener((event) => void received(event.request.content.data, 'foreground'));
        notifications.addNotificationResponseReceivedListener((event) => void received(event.notification.request.content.data, 'tap'));
        notifications.addPushTokenListener((event) => {
          void (async () => {
            const token = await loadToken();
            if (token && event.type === 'android') {
              await registerPushDevice(token, await getPushInstallationId(), 'fcm', String(event.data));
            }
          })().catch(() => console.warn('Não foi possível atualizar o token FCM.'));
        });
      } catch {
        console.warn('Push direto indisponível neste build. Recompile o aplicativo Android.');
      }
    }
  })();
  return initialization;
}

export async function syncPushRegistration(accessToken: string, userId: string) {
  await initializePushNotifications();
  if (Platform.OS !== 'android') return;
  const installationId = await getPushInstallationId();
  const errors: string[] = [];
  if (mode !== 'onesignal') {
    try {
      if (!notifications) throw new Error('Recompile o app para habilitar FCM direto.');
      const permission = await notifications.requestPermissionsAsync();
      if (!permission.granted) throw new Error('Permita as notificações nas configurações do Android.');
      const nativeToken = await notifications.getDevicePushTokenAsync();
      await registerPushDevice(accessToken, installationId, 'fcm', String(nativeToken.data));
      const last = await notifications.getLastNotificationResponseAsync();
      if (last) await received(last.notification.request.content.data, 'tap');
    } catch (error) {
      errors.push(error instanceof Error ? error.message : 'Falha no registro FCM.');
    }
  }
  if (mode !== 'fcm') {
    try {
      const id = await identifyOneSignalUser(userId);
      if (!id) throw new Error('OneSignal ainda não forneceu um identificador.');
      await updateMyOneSignalSubscription(accessToken, id);
      await registerPushDevice(accessToken, installationId, 'onesignal', id);
    } catch { errors.push('Não foi possível registrar o OneSignal.'); }
  }
  if (errors.length) console.warn('Registro push:', errors.join(' '));
  return errors;
}

export async function revokeCurrentPushRegistration() {
  if (Platform.OS !== 'android') return;
  const token = await loadToken();
  if (!token) return;
  try {
    await revokePushDevices(token, await getPushInstallationId());
    await updateMyOneSignalSubscription(token, null);
  } catch { console.warn('Não foi possível revogar push online.'); }
}
