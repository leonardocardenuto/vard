import { NativeModules, PermissionsAndroid, Platform } from 'react-native';
import { mobileMonitorBaseUrl, registerMobileMonitor } from './api';

export type MonitorStatus = {
  running: boolean;
  enabled: boolean;
  sensorAvailable: boolean;
  sensorActive: boolean;
  workspaceId: string | null;
  pendingDeadline: number;
  lastSent: number;
  queued: number;
  error: string;
};

const nativeMonitor = () => Platform.OS === 'android' ? NativeModules.VardFallMonitor : null;
export const monitorAvailable = () => Boolean(nativeMonitor());

export async function monitorStatus(): Promise<MonitorStatus | null> {
  return nativeMonitor()?.status() ?? null;
}

export async function startMobileFallMonitor(accessToken: string, workspaceId: string) {
  const native = nativeMonitor();
  if (!native) throw new Error('Instale a versão Android com monitoramento de quedas.');
  if (Number(Platform.Version) >= 33) {
    const permission = await PermissionsAndroid.request(PermissionsAndroid.PERMISSIONS.POST_NOTIFICATIONS);
    if (permission !== PermissionsAndroid.RESULTS.GRANTED) {
      throw new Error('Permita as notificações para confirmar uma possível queda com a tela bloqueada.');
    }
  }
  const status: MonitorStatus = await native.status();
  if (!status.sensorAvailable) throw new Error('Este aparelho não possui acelerômetro.');
  const device = await registerMobileMonitor(accessToken, workspaceId);
  await native.start(mobileMonitorBaseUrl(), device.device_token, workspaceId);
}

export async function stopMobileFallMonitor() {
  await nativeMonitor()?.stop();
}

export async function cancelMobileFall() {
  await nativeMonitor()?.cancel();
}
